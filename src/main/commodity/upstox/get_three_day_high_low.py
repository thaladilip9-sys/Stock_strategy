import requests
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import os
import upstox_client


load_dotenv('./env/.env.prod')
ACCESS_TOKEN=os.getenv("UPSTOX_ACCESS_TOKEN")

def get_mcx_holidays():
    configuration = upstox_client.Configuration()
    configuration.access_token = ACCESS_TOKEN
    api_instance = upstox_client.MarketHolidaysAndTimingsApi(upstox_client.ApiClient(configuration))
    holidays = set()
    try:
        api_response = api_instance.get_holidays()
        for holiday in api_response['data']:
            holidays.add(holiday['date'])
    except Exception as e:
        print(f"Error loading MCX holidays: {e}")
    return holidays

def simple_trading_strategy(data):
    """Simple trading strategy with MCX holiday exclusion"""
    headers = {'Authorization': f'Bearer {ACCESS_TOKEN}'}
    message = ""

    mcx_holidays = get_mcx_holidays()
    
    # Get last 3 *trading* weekdays (not on holidays)
    weekdays = []
    days_back = 0
    while len(weekdays) < 3:
        date = datetime.now() - timedelta(days=days_back)
        date_str = date.strftime('%Y-%m-%d')
        if date.weekday() < 5 and date_str not in mcx_holidays:
            weekdays.append(date)
        days_back += 1

    instrument_key = data.get('instrument_key')
    highs = []
    lows = []

    message += "📊 Trading Days: " + str([d.strftime('%Y-%m-%d (%a)') for d in weekdays]) + "\n\n"
    message += "🔸 " + data.get('trading_symbol') + ":\n"
    
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
                date_str_fmt = day.strftime('%Y-%m-%d (%a)')
                high_price = candle[2]
                low_price = candle[3]
                message += f"   📈 Day High: {date_str_fmt}: ₹{high_price:.2f}\n"
                message += f"   📉 Day Low: {date_str_fmt}: ₹{low_price:.2f}\n"
            else:
                message += f"   ❌ No candle data for {date_str}\n"
        else:
            message += f"   ❌ Request failed for {date_str} (status {response.status_code})\n"

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
        
        message += f"\n📊 {data.get('trading_symbol')} - 3-Day Analysis\n"
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
    
    return {'message': "❌ No data available (Check holiday and weekend logic!)"}