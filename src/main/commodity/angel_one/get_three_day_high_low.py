# get_three_day_high_low.py
from SmartApi import SmartConnect
import pyotp
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time
from src.main.commodity.angel_one.get_contract_data import  smart_mcx_contracts,get_mcx_instruments

load_dotenv('./env/.env.prod')

def get_angel_one_session():
    """Initialize Angel One session using official SmartApi"""
    try:
        api_key = os.getenv("ANGEL_API_KEY")
        client_id = os.getenv("ANGEL_CLIENT_ID")
        password = os.getenv("ANGEL_PASSWORD")
        totp_secret = os.getenv("ANGEL_TOTP")
        
        smartApi = SmartConnect(api_key)
        
        # Generate TOTP
        totp_secret_clean = ''.join(c for c in totp_secret if c.isalnum()).upper()
        totp = pyotp.TOTP(totp_secret_clean).now()
        
        # Generate session
        data = smartApi.generateSession(client_id, password, totp)
        
        if data['status'] == False:
            print(f"❌ Session generation failed: {data}")
            return None
            
        print("✅ Angel One session created successfully")
        return smartApi
        
    except Exception as e:
        print(f"❌ Error creating Angel One session: {e}")
        return None

def get_trading_days():
    """Get last 3 trading days (excluding weekends)"""
    trading_days = []
    current_date = datetime.now()
    days_back = 1  # Start from yesterday
    
    while len(trading_days) < 3:
        check_date = current_date - timedelta(days=days_back)
        
        # Skip weekends (Saturday=5, Sunday=6)
        if check_date.weekday() < 5:
            trading_days.append(check_date)
        
        days_back += 1
        
        # Safety break
        if days_back > 10:
            break
    
    # Sort dates in ascending order (oldest first)
    trading_days.sort()
    return trading_days

def parse_timestamp(timestamp_str):
    """Parse timestamp from string format '2025-09-24T00:00:00+05:30'"""
    try:
        # Remove timezone part for simplicity
        if 'T' in timestamp_str:
            date_part = timestamp_str.split('T')[0]
            return datetime.strptime(date_part, '%Y-%m-%d')
        else:
            return datetime.strptime(timestamp_str, '%Y-%m-%d')
    except Exception as e:
        print(f"  ❌ Timestamp parsing error: {e}")
        return datetime.now()

def get_historical_data_alternative(smartApi, token, symbol):
    """Alternative method using wider date range - FIXED VERSION"""
    try:
        print(f"🔄 Using alternative method for {symbol}...")
        
        # Get data for last 5 days
        end_date = datetime.now() - timedelta(days=1)  # Yesterday
        start_date = end_date - timedelta(days=7)      # Last 7 days
        
        historicParam = {
            "exchange": "MCX",
            "symboltoken": token,
            "interval": "ONE_DAY",
            "fromdate": start_date.strftime('%Y-%m-%d 09:00'),
            "todate": end_date.strftime('%Y-%m-%d 23:59')
        }
        
        print(f"  Fetching range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Add delay to avoid rate limiting
        time.sleep(2)
        
        historical_data = smartApi.getCandleData(historicParam)
        
        print(f"  Response received: {len(historical_data.get('data', []))} candles")
        
        if historical_data['status'] and historical_data['data']:
            highs = []
            lows = []
            message = f"📊 {symbol} - Historical Analysis\n\n"
            
            # Get last 3 trading days from the data
            recent_candles = historical_data['data'][-3:] if len(historical_data['data']) >= 3 else historical_data['data']
            
            print(f"  Processing {len(recent_candles)} candles...")
            
            for candle in recent_candles:
                try:
                    # Candle format: [timestamp, open, high, low, close, volume]
                    # Timestamp is in string format: '2025-09-24T00:00:00+05:30'
                    timestamp_str = candle[0]
                    high_price = float(candle[2])
                    low_price = float(candle[3])
                    
                    # Parse timestamp
                    timestamp = parse_timestamp(timestamp_str)
                    date_str = timestamp.strftime('%Y-%m-%d')
                    
                    highs.append(high_price)
                    lows.append(low_price)
                    
                    message += f"📈 {date_str} High: ₹{high_price:,.2f}\n"
                    message += f"📉 {date_str} Low: ₹{low_price:,.2f}\n\n"
                    
                    print(f"    ✅ {date_str}: High={high_price:,.2f}, Low={low_price:,.2f}")
                    
                except Exception as e:
                    print(f"    ❌ Error processing candle: {e}")
                    continue
            
            print(f"  ✅ SUCCESS: Processed {len(highs)} days of data")
            return highs, lows, message
        else:
            print(f"  ❌ ALTERNATIVE FAILED: No data - {historical_data}")
            return [], [], f"❌ No historical data available for {symbol}"
            
    except Exception as e:
        print(f"  ❌ ALTERNATIVE ERROR: {e}")
        import traceback
        traceback.print_exc()
        return [], [], f"❌ Error fetching historical data for {symbol}: {e}"

def debug_historical_response(smartApi, token, symbol):
    """Debug function to see the exact response format"""
    try:
        print(f"\n🔍 Debugging response format for {symbol}...")
        
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=3)
        
        historicParam = {
            "exchange": "MCX",
            "symboltoken": token,
            "interval": "ONE_DAY",
            "fromdate": start_date.strftime('%Y-%m-%d 09:00'),
            "todate": end_date.strftime('%Y-%m-%d 23:59')
        }
        
        response = smartApi.getCandleData(historicParam)
        print(f"  Full response: {response}")
        
        if response['status'] and response['data']:
            print(f"  Data structure:")
            for i, candle in enumerate(response['data']):
                print(f"    Candle {i}: {candle}")
                print(f"      Timestamp type: {type(candle[0])}")
                print(f"      Timestamp value: {candle[0]}")
                print(f"      Open: {candle[1]}")
                print(f"      High: {candle[2]}")
                print(f"      Low: {candle[3]}")
                print(f"      Close: {candle[4]}")
                print(f"      Volume: {candle[5]}")
        
        return response
        
    except Exception as e:
        print(f"  ❌ Debug error: {e}")
        return None

def get_spot_commodity_data(smartApi, symbol):
    """Try to get spot commodity data instead of futures"""
    try:
        print(f"🔍 Trying spot data for {symbol}...")
        
        # Map futures symbols to likely spot symbols
        spot_symbols = {
            'GOLDM': 'GOLD',
            'SILVERM': 'SILVER'
        }
        
        base_symbol = spot_symbols.get(symbol.split('FUT')[0])
        if not base_symbol:
            return [], [], "❌ No spot symbol mapping found"
        
        # Get spot instruments
        # from get_contract_data import get_mcx_instruments
        instruments = get_mcx_instruments()
        if not instruments:
            return [], [], "❌ Could not fetch instruments"
        
        # Find spot contract
        spot_contracts = [
            inst for inst in instruments 
            if inst.get('symbol') == base_symbol and inst.get('exch_seg') == 'MCX'
        ]
        
        if not spot_contracts:
            print(f"  ❌ No spot contract found for {base_symbol}")
            # Try GOLDPETAL for gold
            if base_symbol == 'GOLD':
                spot_contracts = [inst for inst in instruments if 'GOLDPETAL' in inst.get('symbol', '')]
            elif base_symbol == 'SILVER':
                spot_contracts = [inst for inst in instruments if 'SILVERPETAL' in inst.get('symbol', '')]
        
        if not spot_contracts:
            return [], [], f"❌ No spot contract found for {base_symbol}"
        
        spot_token = spot_contracts[0].get('token')
        spot_symbol_name = spot_contracts[0].get('symbol')
        print(f"  Found spot contract: {spot_symbol_name} (Token: {spot_token})")
        
        # Get historical data for spot
        return get_historical_data_alternative(smartApi, spot_token, f"{spot_symbol_name}_SPOT")
        
    except Exception as e:
        print(f"  ❌ SPOT DATA ERROR: {e}")
        return [], [], f"❌ Error fetching spot data: {e}"

def calculate_trading_levels(highs, lows, symbol, token):
    """Calculate trading levels based on historical high/low"""
    
    if not highs or not lows:
        return None, "❌ Insufficient data to calculate trading levels"
    
    three_day_high = max(highs)
    three_day_low = min(lows)
    price_range = three_day_high - three_day_low
    
    message = f"🎯 {symbol} - TRADING LEVELS\n"
    message += "=" * 40 + "\n"
    message += f"📈 3-Day High: ₹{three_day_high:,.2f}\n"
    message += f"📉 3-Day Low: ₹{three_day_low:,.2f}\n"
    message += f"📊 Price Range: ₹{price_range:,.2f}\n\n"
    
    # Calculate trading levels
    buy_entry = three_day_low + (price_range * 0.1)
    buy_target = buy_entry + (price_range * 0.15)
    buy_sl = buy_entry - (price_range * 0.05)
    
    sell_entry = three_day_high - (price_range * 0.1)
    sell_target = sell_entry - (price_range * 0.15)
    sell_sl = sell_entry + (price_range * 0.05)
    
    message += "🟢 BUY STRATEGY\n"
    message += f"Entry: ₹{buy_entry:,.2f}\n"
    message += f"Target: ₹{buy_target:,.2f} (+{((buy_target-buy_entry)/buy_entry*100):.1f}%)\n"
    message += f"SL: ₹{buy_sl:,.2f} ({((buy_sl-buy_entry)/buy_entry*100):.1f}%)\n\n"
    
    message += "🔴 SELL STRATEGY\n"
    message += f"Entry: ₹{sell_entry:,.2f}\n"
    message += f"Target: ₹{sell_target:,.2f} ({((sell_target-sell_entry)/sell_entry*100):.1f}%)\n"
    message += f"SL: ₹{sell_sl:,.2f} ({((sell_sl-sell_entry)/sell_entry*100):.1f}%)\n"
    
    strategy_data = {
        'three_day_high': three_day_high,
        'three_day_low': three_day_low,
        'buy_entry': buy_entry,
        'buy_target': buy_target,
        'buy_sl': buy_sl,
        'sell_entry': sell_entry,
        'sell_target': sell_target,
        'sell_sl': sell_sl,
        'token': token
    }
    
    return strategy_data, message

def analyze_symbol(smartApi, symbol_data):
    """Analyze a single symbol and return trading levels"""
    symbol = symbol_data.get('symbol')
    token = symbol_data.get('token')
    
    print(f"\n🔍 Analyzing {symbol}...")
    
    # First, debug the response format
    debug_response = debug_historical_response(smartApi, token, symbol)
    
    # Use alternative method (which now works with the timestamp format)
    highs, lows, historical_message = get_historical_data_alternative(smartApi, token, symbol)
    
    # If still no data, try spot data
    if not highs or not lows:
        print(f"🔄 Futures data failed, trying spot data for {symbol}...")
        highs, lows, historical_message = get_spot_commodity_data(smartApi, symbol)
    
    if not highs or not lows:
        return None, f"❌ Could not fetch sufficient data for {symbol}"
    
    # Calculate trading levels
    strategy_data, levels_message = calculate_trading_levels(highs, lows, symbol, token)
    
    full_message = historical_message + levels_message
    
    # Add strategy data to symbol data
    if strategy_data:
        symbol_data.update(strategy_data)
    
    return symbol_data, full_message

def main_analysis():
    """Main function to analyze GOLDM and SILVERM"""
    
    # Get Angel One session
    smartApi = get_angel_one_session()
    if not smartApi:
        return "❌ Failed to connect to Angel One", []
    
    # Get MCX contracts
    # from get_contract_data import smart_mcx_contracts
    goldm_data, silverm_data = smart_mcx_contracts()
    
    if not goldm_data and not silverm_data:
        return "❌ No valid contracts found for analysis", []
    
    results = []
    
    # Analyze GOLDM with delay between requests
    if goldm_data:
        goldm_result, goldm_message = analyze_symbol(smartApi, goldm_data)
        if goldm_result:
            results.append(("GOLDM", goldm_message, goldm_result))
        
        # Add delay between symbol requests
        time.sleep(3)
    
    # Analyze SILVERM
    if silverm_data:
        silverm_result, silverm_message = analyze_symbol(smartApi, silverm_data)
        if silverm_result:
            results.append(("SILVERM", silverm_message, silverm_result))
    
    # Generate final report
    final_report = "🎯 MCX COMMODITY ANALYSIS REPORT\n"
    final_report += "=" * 50 + "\n\n"
    
    for symbol_name, message, data in results:
        final_report += f"#{symbol_name}\n"
        final_report += message + "\n" + "="*50 + "\n\n"
    
    return final_report, results

# if __name__ == "__main__":
#     print("🚀 Starting MCX Commodity Analysis...")
#     report, data_results = main_analysis()
#     print(report)
    
#     # Print structured data
#     if data_results:
#         print("\n📊 STRUCTURED DATA:")
#         for symbol_name, message, data in data_results:
#             print(f"\n{symbol_name}:")
#             print(f"  High: ₹{data.get('three_day_high', 0):,.2f}")
#             print(f"  Low: ₹{data.get('three_day_low', 0):,.2f}")
#             print(f"  Buy Entry: ₹{data.get('buy_entry', 0):,.2f}")
#             print(f"  Sell Entry: ₹{data.get('sell_entry', 0):,.2f}")
#     else:
#         print("\n❌ No data results available")