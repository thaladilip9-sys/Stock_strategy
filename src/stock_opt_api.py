# fastapi_trading_monitor.py

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import threading
import time
import logging
from datetime import datetime, time as dt_time, date, timedelta
import asyncio
from typing import Dict, Optional, Set, AsyncGenerator
import os
import requests
import gc
import psutil
import tracemalloc
from dotenv import load_dotenv

# Import your existing monitor
from src.main.interaday_stock_options.angel_one.live_option_monitor import main as start_live_monitor
from src.main.interaday_stock_options.angel_one.live_option_monitor import ParallelOptionMonitor

from src.utils.get_active_market_days import MarketHolidayManager,TradingHoursManager
from src.main.interaday_stock_options.services.manage_monitor import MonitorManager

from src.utils.send_message import send_telegram_message_admin

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fastapi_trading_monitor.log'),
        logging.StreamHandler()
    ]
)

load_dotenv('./env/.env.prod')

# Initialize managers
holiday_manager = MarketHolidayManager()
trading_hours_manager = TradingHoursManager(holiday_manager)
monitor_manager = MonitorManager(trading_hours_manager)

# Memory monitoring
tracemalloc.start()

def get_memory_usage():
    """Get current memory usage"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    return {
        "rss_mb": memory_info.rss / 1024 / 1024,
        "vms_mb": memory_info.vms / 1024 / 1024,
        "percent": process.memory_percent()
    }

def force_garbage_collection():
    """Force garbage collection and return memory stats"""
    gc.collect()
    memory_before = get_memory_usage()
    
    # Collect garbage
    collected = gc.collect()
    
    memory_after = get_memory_usage()
    
    logging.info(f"🧹 Garbage collection: {collected} objects collected")
    logging.info(f"💾 Memory - Before: {memory_before['rss_mb']:.2f} MB, After: {memory_after['rss_mb']:.2f} MB")
    
    return memory_after

async def run_stock_analysis():
    """Run stock options analysis at 8:00 PM"""
    try:
        logging.info("🔄 Starting scheduled stock options analysis...")
        
        from src.main.interaday_stock_options.angel_one.stock_options_analysis import UpdateStockOptData
        
        # Force garbage collection before starting
        force_garbage_collection()
        
        analyzer = UpdateStockOptData()
        result = analyzer.run()
        
        # Force garbage collection after completion
        force_garbage_collection()
        
        logging.info(f"✅ Stock options analysis completed: {result}")
        return result
        
    except Exception as e:
        logging.error(f"❌ Stock options analysis failed: {e}")
        # Force garbage collection even on failure
        force_garbage_collection()
        return None

async def scheduled_tasks_manager():
    """Manage all scheduled tasks"""
    while True:
        try:
            now = datetime.now()
            current_time = now.time()
            
            # Schedule stock analysis at 8:00 PM (20:00)
            if current_time.hour == 20 and current_time.minute == 0 and current_time.second == 0:
                logging.info("⏰ 8:00 PM - Triggering stock options analysis")
                asyncio.create_task(run_stock_analysis())
                
                # Sleep for 61 seconds to avoid multiple triggers in the same minute
                await asyncio.sleep(61)
            
            # Memory cleanup every hour
            if current_time.minute == 0 and current_time.second == 0:
                memory_stats = force_garbage_collection()
                logging.info(f"🕐 Hourly memory cleanup: {memory_stats['rss_mb']:.2f} MB")
                
                # Sleep for 61 seconds to avoid multiple triggers in the same minute
                await asyncio.sleep(61)
            
            # Default sleep
            await asyncio.sleep(1)
            
        except Exception as e:
            logging.error(f"Error in scheduled tasks manager: {e}")
            await asyncio.sleep(60)

async def trading_hours_scheduler():
    """Background task to automatically start/stop monitor based on trading hours"""
    while True:
        try:
            current_time = datetime.now()
            is_trading_hours = trading_hours_manager.is_trading_hours()
            is_trading_day = holiday_manager.is_trading_day()
            
            should_monitor_run = is_trading_day and is_trading_hours
            is_monitor_running = monitor_manager.is_running
            
            # Debug logging
            if current_time.second == 0:  # Log every minute for visibility
                logging.info(f"🔄 Auto-sync check: TradingDay={is_trading_day}, TradingHours={is_trading_hours}, ShouldRun={should_monitor_run}, IsRunning={is_monitor_running}")
                send_telegram_message_admin(f"🔄 Auto-sync check at {current_time.isoformat()}: TradingDay={is_trading_day}, TradingHours={is_trading_hours}, ShouldRun={should_monitor_run}, IsRunning={is_monitor_running}")
            
            # Sync the monitor state with trading conditions
            if should_monitor_run and not is_monitor_running:
                # Should be running but isn't - start it
                logging.info("🚀 *AUTO-START:* Starting monitor (trading conditions met)")
                send_telegram_message_admin("🚀 *AUTO-START:* Starting monitor (trading conditions met)")
                success = monitor_manager.start_monitor()
                if success:
                    logging.info("✅ *AUTO-START:* Monitor started successfully")
                    send_telegram_message_admin("✅ *AUTO-START:* Monitor started successfully")
                else:
                    logging.error("❌ AUTO-START: Failed to start monitor")
                    send_telegram_message_admin("❌ *AUTO-START:* Failed to start monitor")
            
            elif not should_monitor_run and is_monitor_running:
                # Should be stopped but is running - stop it
                reason = "not a trading day" if not is_trading_day else "outside trading hours"
                logging.info(f"🛑 AUTO-STOP: Stopping monitor ({reason})")
                send_telegram_message_admin(f"🛑 *AUTO-STOP:* Stopping monitor ({reason})")
                success = monitor_manager.stop_monitor()
                if success:
                    logging.info("✅ AUTO-STOP: Monitor stopped successfully")
                    send_telegram_message_admin("✅ *AUTO-STOP:* Monitor stopped successfully")
                    # Force garbage collection when monitor stops
                    force_garbage_collection()
                else:
                    logging.error("❌ AUTO-STOP: Failed to stop monitor")
                    send_telegram_message_admin("❌ *AUTO-STOP:* Failed to stop monitor")
            
            # Wait before next check
            await asyncio.sleep(30)  # Check every 30 seconds for faster response
            
        except Exception as e:
            logging.error(f"❌ Error in trading hours scheduler: {e}")
            send_telegram_message_admin(f"❌ Error in trading hours scheduler: {e}")
            await asyncio.sleep(60)  # Wait 1 minute on error


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager to replace on_event"""
    # Startup code
    logging.info("🚀 Starting FastAPI Trading Hours Monitor Controller")
    send_telegram_message_admin(f"🚀 *Starting FastAPI Trading Hours Monitor Controller*")
    
    
    # Initial memory cleanup
    initial_memory = force_garbage_collection()
    logging.info(f"💾 Initial memory usage: {initial_memory['rss_mb']:.2f} MB")
    send_telegram_message_admin(f"💾 Initial memory usage: {initial_memory['rss_mb']:.2f} MB")
    
    # Pre-fetch holidays for current year
    current_year = datetime.now().year
    holiday_manager.fetch_holidays(current_year)
    
    # Perform initial sync to ensure monitor is in correct state
    logging.info("🔄 Performing initial monitor sync...")
    send_telegram_message_admin("🔄 *Performing initial monitor sync...*")
    is_trading_day = holiday_manager.is_trading_day()
    is_trading_hours = trading_hours_manager.is_trading_hours()
    should_run = is_trading_day and is_trading_hours
    
    if should_run and not monitor_manager.is_running:
        logging.info("🔰 Initial sync: Starting monitor")
        send_telegram_message_admin("🔰 *Initial sync:* Starting monitor")
        monitor_manager.start_monitor()
    elif not should_run and monitor_manager.is_running:
        logging.info("🔰 Initial sync: Stopping monitor")
        send_telegram_message_admin("🔰 *Initial sync:* Stopping monitor")
        monitor_manager.stop_monitor()
    else:
        logging.info("🔰 Initial sync: Monitor already in correct state")
        send_telegram_message_admin("🔰 *Initial sync:* Monitor already in correct state")
    
    # Start background schedulers
    trading_scheduler_task = asyncio.create_task(trading_hours_scheduler())
    scheduled_tasks_task = asyncio.create_task(scheduled_tasks_manager())
    
    yield  # App runs here
    
    # Shutdown code
    logging.info("🛑 Shutting down FastAPI Trading Hours Monitor Controller")
    send_telegram_message_admin("🛑 *Shutting down FastAPI Trading Hours Monitor Controller*")
    
    # Cancel all background tasks
    trading_scheduler_task.cancel()
    scheduled_tasks_task.cancel()
    
    try:
        await asyncio.gather(trading_scheduler_task, scheduled_tasks_task, return_exceptions=True)
    except Exception as e:
        logging.error(f"Error during shutdown: {e}")
        send_telegram_message_admin(f"❌ Error during shutdown: {e}")
    
    # Stop monitor and cleanup
    monitor_manager.stop_monitor()
    
    # Final memory cleanup
    final_memory = force_garbage_collection()
    logging.info(f"💾 Final memory usage: {final_memory['rss_mb']:.2f} MB")
    send_telegram_message_admin(f"💾 Final memory usage: {final_memory['rss_mb']:.2f} MB")

app = FastAPI(
    title="Trading Hours Live Option Monitor API",
    description="API to control live option monitoring during trading hours and active trading days",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint with API information"""
    memory_stats = get_memory_usage()
    return {
        "message": "Trading Hours Live Option Monitor API",
        "status": "running",
        "memory_usage_mb": round(memory_stats['rss_mb'], 2),
        "features": [
            "Automatic holiday detection",
            "Trading hours enforcement", 
            "Real-time market status",
            "Manual monitor control",
            "Scheduled stock analysis (8:00 PM)",
            "Memory optimization"
        ],
        "endpoints": {
            "status": "GET /status - Get monitor status",
            "start": "POST /start - Start monitor manually",
            "stop": "POST /stop - Stop monitor manually",
            "trading_info": "GET /trading-info - Get trading hours and holidays",
            "health": "GET /health - Health check",
            "memory": "GET /memory - Memory usage info",
            "run_analysis": "POST /run-analysis - Run stock analysis manually"
        }
    }

@app.get("/status")
async def get_status():
    """Get current monitor and market status"""
    status = monitor_manager.get_status()
    memory_stats = get_memory_usage()
    is_trading_day = holiday_manager.is_trading_day()
    is_trading_hours = trading_hours_manager.is_trading_hours()
    
    # Determine if monitor should be running
    should_monitor_run = is_trading_day and is_trading_hours
    monitor_status = "RUNNING" if monitor_manager.is_running else "STOPPED"
    expected_status = "SHOULD BE RUNNING" if should_monitor_run else "SHOULD BE STOPPED"
    
    status.update({
        "memory_usage": {
            "rss_mb": round(memory_stats['rss_mb'], 2),
            "vms_mb": round(memory_stats['vms_mb'], 2),
            "percent": round(memory_stats['percent'], 2)
        },
        "trading_conditions": {
            "is_trading_day": is_trading_day,
            "is_trading_hours": is_trading_hours,
            "should_monitor_run": should_monitor_run,
            "actual_monitor_status": monitor_status,
            "expected_monitor_status": expected_status,
            "is_synchronized": (monitor_manager.is_running == should_monitor_run)
        },
        "trading_hours": {
            "is_market_open": is_trading_hours,
            "market_open_time": trading_hours_manager.MARKET_OPEN.isoformat(),
            "market_close_time": trading_hours_manager.MARKET_CLOSE.isoformat(),
            "seconds_until_open": trading_hours_manager.time_until_market_open(),
            "seconds_until_close": trading_hours_manager.time_until_market_close()
        },
        "trading_day": {
            "is_trading_day": is_trading_day,
            "today": date.today().isoformat(),
            "next_trading_day": holiday_manager.get_next_trading_day().isoformat()
        },
        "scheduled_tasks": {
            "next_analysis": "20:00:00 daily",
            "next_memory_cleanup": "Next hour",
            "next_trading_check": "Every minute"
        }
    })
    return status


@app.post("/sync-monitor")
async def sync_monitor():
    """Force synchronization of monitor with current trading conditions"""
    try:
        is_trading_day = holiday_manager.is_trading_day()
        is_trading_hours = trading_hours_manager.is_trading_hours()
        should_run = is_trading_day and is_trading_hours
        
        if should_run and not monitor_manager.is_running:
            # Should be running but isn't - start it
            logging.info("🔄 Syncing: Starting monitor (should be running)")
            success = monitor_manager.start_monitor()
            if success:
                return {
                    "message": "Monitor started successfully",
                    "action": "started",
                    "reason": "Trading conditions met"
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to start monitor")
        
        elif not should_run and monitor_manager.is_running:
            # Should be stopped but is running - stop it
            logging.info("🔄 Syncing: Stopping monitor (should be stopped)")
            success = monitor_manager.stop_monitor()
            if success:
                force_garbage_collection()
                return {
                    "message": "Monitor stopped successfully", 
                    "action": "stopped",
                    "reason": "Trading conditions not met"
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to stop monitor")
        else:
            # Already in correct state
            return {
                "message": "Monitor is already in correct state",
                "action": "none",
                "reason": "Already synchronized"
            }
            
    except Exception as e:
        logging.error(f"Sync error: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@app.post("/start")
async def start_monitor():
    """Start the monitor manually (only during trading hours)"""
    if monitor_manager.is_running:
        raise HTTPException(status_code=400, detail="Monitor is already running")
    
    if not trading_hours_manager.is_trading_hours():
        raise HTTPException(
            status_code=400, 
            detail="Cannot start monitor outside trading hours. Market is closed."
        )
    
    success = monitor_manager.start_monitor()
    if success:
        return {"message": "Monitor started successfully", "status": "running"}
    else:
        raise HTTPException(status_code=500, detail="Failed to start monitor")

@app.post("/stop")
async def stop_monitor():
    """Stop the monitor manually"""
    if not monitor_manager.is_running:
        raise HTTPException(status_code=400, detail="Monitor is not running")
    
    success = monitor_manager.stop_monitor()
    if success:
        # Force garbage collection when manually stopped
        force_garbage_collection()
        return {"message": "Monitor stopped successfully", "status": "stopped"}
    else:
        raise HTTPException(status_code=500, detail="Failed to stop monitor")

@app.get("/trading-info")
async def get_trading_info():
    """Get trading hours and holiday information"""
    current_year = datetime.now().year
    holidays = holiday_manager.fetch_holidays(current_year)
    
    return {
        "current_year": current_year,
        "trading_hours": {
            "open": trading_hours_manager.MARKET_OPEN.isoformat(),
            "close": trading_hours_manager.MARKET_CLOSE.isoformat(),
            "timezone": "IST"
        },
        "trading_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        "holidays": sorted([h.isoformat() for h in holidays]),
        "next_trading_day": holiday_manager.get_next_trading_day().isoformat(),
        "market_status": "OPEN" if trading_hours_manager.is_trading_hours() else "CLOSED"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    memory_stats = get_memory_usage()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "monitor_running": monitor_manager.is_running,
        "market_open": trading_hours_manager.is_trading_hours(),
        "trading_day": holiday_manager.is_trading_day(),
        "memory_usage_mb": round(memory_stats['rss_mb'], 2),
        "memory_percent": round(memory_stats['percent'], 2)
    }

@app.get("/next-trading-day")
async def get_next_trading_day():
    """Get information about the next trading day"""
    next_day = holiday_manager.get_next_trading_day()
    return {
        "next_trading_day": next_day.isoformat(),
        "days_until": (next_day - date.today()).days,
        "day_of_week": next_day.strftime("%A")
    }

@app.get("/memory")
async def get_memory_info():
    """Get detailed memory usage information"""
    memory_stats = get_memory_usage()
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')[:10]
    
    top_allocations = []
    for stat in top_stats:
        top_allocations.append({
            "file": str(stat.traceback[0]),
            "size_kb": stat.size / 1024,
            "count": stat.count
        })
    
    return {
        "current_usage": memory_stats,
        "garbage_collection": {
            "enabled": gc.isenabled(),
            "threshold": gc.get_threshold(),
            "count": gc.get_count()
        },
        "top_allocations": top_allocations
    }

@app.post("/run-analysis")
async def run_analysis_now():
    """Run stock options analysis manually"""
    try:
        result = await run_stock_analysis()
        if result:
            return {"message": "Stock analysis completed successfully", "result": result}
        else:
            raise HTTPException(status_code=500, detail="Stock analysis failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")

@app.post("/cleanup-memory")
async def cleanup_memory():
    """Force garbage collection and memory cleanup"""
    memory_stats = force_garbage_collection()
    return {
        "message": "Memory cleanup completed",
        "memory_usage_mb": round(memory_stats['rss_mb'], 2),
        "memory_percent": round(memory_stats['percent'], 2)
    }

# if __name__ == "__main__":
#     # Run the FastAPI server
#     uvicorn.run(
#         "fastapi_trading_monitor:app",
#         host="0.0.0.0",
#         port=8000,
#         reload=True,
#         log_level="info"
#     )