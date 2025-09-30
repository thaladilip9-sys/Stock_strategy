# main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import json
from datetime import datetime

# Import your existing function
from src.main.commodity.angel_one.get_three_day_high_low import main_analysis

# JSON file to store results
ANALYSIS_JSON_FILE = 'commodity_data.json'

def save_to_json(data_results):
    """Save analysis results to JSON file"""
    try:
        data_to_save = {
            'last_updated': datetime.now().isoformat(),
            'data': []
        }
        
        for symbol_name, message, data in data_results:
            data_to_save['data'].append({
                'symbol': symbol_name,
                'three_day_high': data.get('three_day_high'),
                'three_day_low': data.get('three_day_low'),
                'buy_entry': data.get('buy_entry'),
                'buy_target': data.get('buy_target'),
                'buy_sl': data.get('buy_sl'),
                'sell_entry': data.get('sell_entry'),
                'sell_target': data.get('sell_target'),
                'sell_sl': data.get('sell_sl'),
                'message': message,
                'token': data.get('token')
            })
        
        with open(ANALYSIS_JSON_FILE, 'w') as f:
            json.dump(data_to_save, f, indent=2)
        
        print(f"✅ Data saved to {ANALYSIS_JSON_FILE}")
        
    except Exception as e:
        print(f"❌ Error saving to JSON: {e}")

def scheduled_analysis():
    """Function to run analysis and save to JSON"""
    print(f"\n⏰ Running scheduled analysis at {datetime.now().strftime('%H:%M:%S')}")
    
    try:
        # Use your existing function
        report, data_results = main_analysis()
        
        # Print the report
        print(report)
        
        # Save to JSON
        if data_results:
            save_to_json(data_results)
        else:
            print("❌ No data results to save")
            
    except Exception as e:
        print(f"❌ Analysis failed: {e}")

# Initialize scheduler
scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    scheduler.add_job(
        scheduled_analysis,
        trigger=CronTrigger(hour=8, minute=15),
        id='daily_analysis'
    )
    scheduler.start()
    print("🚀 Commodity Analysis API Started")
    print("⏰ Scheduler running - will execute daily at 23:40 (11:40 PM)")
    
    yield
    
    # Shutdown
    scheduler.shutdown()
    print("🛑 Scheduler stopped")

app = FastAPI(title="Commodity Analysis API", lifespan=lifespan)

@app.get("/")
def read_root():
    return {"message": "Commodity Analysis API is running"}

@app.get("/run-now")
def run_analysis_now():
    """Endpoint to manually trigger analysis"""
    scheduled_analysis()
    return {"message": "Analysis completed manually"}

@app.get("/status")
def get_status():
    """Get current status and last run info"""
    try:
        with open(ANALYSIS_JSON_FILE, 'r') as f:
            data = json.load(f)
        return {
            "status": "running",
            "last_updated": data.get('last_updated'),
            "data_available": len(data.get('data', []))
        }
    except:
        return {"status": "running", "last_updated": "Never", "data_available": 0}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)