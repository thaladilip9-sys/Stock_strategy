import requests
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import os
load_dotenv('./env/.env.prod')
ACCESS_TOKEN=os.getenv("UPSTOX_ACCESS_TOKEN")

def simple_trading_strategy(data):
    """Simple trading strategy exactly as requested"""
    
    headers = {'Authorization': f'Bearer {ACCESS_TOKEN}'}
    message = ""
    
    # Get last 3 weekdays
    weekdays = []
    days_back = 0
    while len(weekdays) < 3:
        date = datetime.now() - timedelta(days=days_back)
        if date.weekday() < 5:  # Monday to Friday
            weekdays.append(date)
        days_back += 1
    
    instrument_key = data.get('instrument_key')
    highs = []
    lows = []

    message +="📊 Trading Days: "+str([d.strftime('%Y-%m-%d (%a)') for d in weekdays]) +"\n\n"
    
    message +="🔸 "+data.get('trading_symbol')+":\n"
    # Fetch 3-day high/low
    for day in weekdays:
        date_str = day.strftime('%Y-%m-%d')
        url = f"https://api.upstox.com/v2/historical-candle/{instrument_key}/day/{date_str}/{date_str}"
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            candle_data = response.json()
            if candle_data.get('data', {}).get('candles'):
                candle = candle_data['data']['candles'][0]
                highs.append(candle[2])  # High
                lows.append(candle[3])   # Low
                date_str = day.strftime('%Y-%m-%d (%a)')
                high_price = candle_data['data']['candles'][0][2]
                message +="   📈 "+"Day High: "+date_str+": ₹"+str(f"{high_price:.2f}")+"\n\n"

                low_price = candle_data['data']['candles'][0][3]
    message+="="*40 +"\n"
    for day in weekdays:
        date_str = day.strftime('%Y-%m-%d')
        url = f"https://api.upstox.com/v2/historical-candle/{instrument_key}/day/{date_str}/{date_str}"
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            candle_data = response.json()
            if candle_data.get('data', {}).get('candles'):
                candle = candle_data['data']['candles'][0]
                highs.append(candle[2])  # High
                lows.append(candle[3])   # Low
                date_str = day.strftime('%Y-%m-%d (%a)')

                low_price = candle_data['data']['candles'][0][3]
                message +="   📉 "+"Day Low: "+date_str+": ₹"+str(f"{low_price:.2f}")+"\n\n"
    
    if highs and lows:
        three_day_high = max(highs)
        three_day_low = min(lows)
        
        # BUY STRATEGY (Based on 3-day high)
        buy_entry = three_day_high * 0.12
        buy_target = buy_entry * 1.5
        buy_sl = buy_entry * -1.5
        
        # SELL STRATEGY (Based on 3-day low)
        sell_entry = three_day_low * 0.12
        sell_target = sell_entry * -1.5
        sell_sl = sell_entry * 1.5
        
        message += f"📊 {data.get('trading_symbol')} - 3-Day Analysis\n"
        message += f"📈 3-Day High: ₹{three_day_high:.2f}\n"
        message += f"📉 3-Day Low: ₹{three_day_low:.2f}\n\n"
        
        message += "🟢 BUY STRATEGY\n"
        message += f"Entry: 3-Day High × 0.12 = ₹{buy_entry:.2f}\n"
        message += f"Target: Entry × 1.5 = ₹{buy_target:.2f}\n"
        message += f"SL: Entry × -1.5 = ₹{buy_sl:.2f}\n\n"
        
        message += "🔴 SELL STRATEGY\n"
        message += f"Entry: 3-Day Low × 0.12 = ₹{sell_entry:.2f}\n"
        message += f"Target: Entry × -1.5 = ₹{sell_target:.2f}\n"
        message += f"SL: Entry × 1.5 = ₹{sell_sl:.2f}\n"
        
        return {
            'three_day_high': three_day_high,
            'three_day_low': three_day_low,
            'buy_entry': buy_entry,
            'buy_target': buy_target, 
            'buy_sl': buy_sl,
            'sell_entry': sell_entry,
            'sell_target': sell_target,
            'sell_sl': sell_sl,
            'message': message
        }
    
    return {'message': "❌ No data available"}
