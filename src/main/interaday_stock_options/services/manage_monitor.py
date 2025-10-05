import threading
import time
import logging
from datetime import datetime, time as dt_time, date, timedelta
import asyncio
from typing import Dict, Optional, Set
from src.main.interaday_stock_options.angel_one.live_option_monitor import main, ParallelOptionMonitor



class MonitorManager:
    """Manage the live option monitor instance"""
    
    def __init__(self, trading_hours_manager:classmethod):
        self.trading_hours_manager = trading_hours_manager
        self.monitor_thread = None
        self.is_running = False
        self.last_start_time = None
        self.last_stop_time = None
        self.monitor_instance = None
        
    def start_monitor(self) -> bool:
        """Start the live option monitor"""
        try:
            if self.is_running:
                logging.warning("Monitor is already running")
                return True
            
            if not self.trading_hours_manager.is_trading_hours():
                logging.error("Cannot start monitor outside trading hours")
                return False
            
            # Start monitor in a separate thread
            self.monitor_thread = threading.Thread(
                target=self._run_monitor,
                daemon=True,
                name="LiveOptionMonitor"
            )
            self.monitor_thread.start()
            
            self.is_running = True
            self.last_start_time = datetime.now()
            logging.info("✅ Live option monitor started successfully")
            return True
            
        except Exception as e:
            logging.error(f"❌ Failed to start monitor: {e}")
            return False
    
    def _run_monitor(self):
        """Internal method to run the monitor"""
        try:
            # Import and run your main function
            self.monitor_instance = ParallelOptionMonitor()
            main()  # This will run your existing monitoring logic
            
        except Exception as e:
            logging.error(f"Monitor execution error: {e}")
        finally:
            self.is_running = False
            self.last_stop_time = datetime.now()
    
    def stop_monitor(self) -> bool:
        """Stop the live option monitor"""
        try:
            if not self.is_running:
                logging.warning("Monitor is not running")
                return True
            
            if self.monitor_instance:
                self.monitor_instance.stop_monitoring()
            
            self.is_running = False
            self.last_stop_time = datetime.now()
            logging.info("✅ Live option monitor stopped successfully")
            return True
            
        except Exception as e:
            logging.error(f"❌ Failed to stop monitor: {e}")
            return False
    
    def get_status(self) -> Dict:
        """Get current monitor status"""
        status = {
            "is_running": self.is_running,
            "last_start_time": self.last_start_time.isoformat() if self.last_start_time else None,
            "last_stop_time": self.last_stop_time.isoformat() if self.last_stop_time else None,
            "market_status": "OPEN" if self.trading_hours_manager.is_trading_hours() else "CLOSED",
            "current_time": datetime.now().isoformat(),
            "is_trading_day": self.trading_hours_manager.holiday_manager.is_trading_day()
        }
        
        return status