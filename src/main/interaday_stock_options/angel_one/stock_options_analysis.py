# smartapi_stock_analysis_fixed.py
from SmartApi import SmartConnect
import pyotp
import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
import pandas as pd
from src.utils.get_chartlink_data import fetch_chartink_data
from src.utils.search_your_stocks import get_stock_details
import time
from src.utils.angel_one_connect import AngelOneConnect
from src.utils.send_message import send_telegram_message


load_dotenv('./env/.env.prod')

class UpdateStockOptData:
    def __init__(self):
        self.smart_api = None
        self.min_price = 1000  # Filter stocks above ₹1000
        self.connect_instance = AngelOneConnect()
        self.smart_api = self.connect_instance.connect()
        
    # def create_session(self):
    #     """Create Angel One session"""
    #     try:
    #         api_key = os.getenv("ANGEL_API_KEY")
    #         client_id = os.getenv("ANGEL_CLIENT_ID")
    #         password = os.getenv("ANGEL_PASSWORD")
    #         totp_secret = os.getenv("ANGEL_TOTP")
            
    #         self.smart_api = SmartConnect(api_key)
            
    #         # Generate TOTP
    #         totp_secret_clean = ''.join(c for c in totp_secret if c.isalnum()).upper()
    #         totp = pyotp.TOTP(totp_secret_clean).now()
            
    #         # Generate session
    #         data = self.smart_api.generateSession(client_id, password, totp)
            
    #         if data['status'] == False:
    #             print(f"❌ Session generation failed: {data}")
    #             return False
                
    #         print("✅ Angel One session created successfully")
    #         return True
            
    #     except Exception as e:
    #         print(f"❌ Error creating session: {e}")
    #         return False
    
    def get_historical_data(self, symbol_token, exchange="NSE"):
        """Get historical OHLC data for the stock"""
        try:
            # Use current date
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)  # Get last 7 days data
            
            historicParam = {
                "exchange": exchange,
                "symboltoken": symbol_token,
                "interval": "ONE_DAY",
                "fromdate": start_date.strftime('%Y-%m-%d 09:00'),
                "todate": end_date.strftime('%Y-%m-%d 15:30')
            }
            
            print(f"   📅 Fetching OHLC data for {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            
            # Add delay to avoid rate limiting
            time.sleep(1)
            
            historical_data = self.smart_api.getCandleData(historicParam)
            
            if historical_data['status'] and historical_data['data']:
                # Get the latest candle (today's data)
                latest_candle = historical_data['data'][-1]
                return {
                    'open': float(latest_candle[1]),
                    'high': float(latest_candle[2]),
                    'low': float(latest_candle[3]),
                    'close': float(latest_candle[4]),
                    'volume': float(latest_candle[5])
                }
            else:
                print(f"   ❌ No historical data received")
                return None
                
        except Exception as e:
            print(f"   ❌ Historical data error: {e}")
            return None

    def get_option_day_high_low(self, option_data):
        """Get day high and low for selected options"""
        try:
            if not option_data or 'token' not in option_data:
                return None
                
            # Get historical data for the option
            option_historical = self.get_historical_data(option_data['token'], "NFO")
            
            if option_historical:
                return {
                    'day_high': option_historical['high'],
                    'day_low': option_historical['low'],
                    'day_open': option_historical['open'],
                    'day_close': option_historical['close']
                }
            else:
                print(f"   ❌ Could not fetch OHLC data for option {option_data['symbol']}")
                return None
                
        except Exception as e:
            print(f"   ❌ Error fetching option OHLC data: {e}")
            return None

    def calculate_trading_levels(self, option_day_high, current_ltp):
        """Calculate trading levels based on option day high"""
        try:
            # Buy Entry: Above option day high
            buy_entry = option_day_high + 0.01  # Just above day high
            
            # Target: Option day high + 5%
            target = option_day_high * 1.05
            
            # Stoploss: Option day high - 5%
            stoploss = option_day_high * 0.95
            
            # Calculate risk-reward ratio
            risk = buy_entry - stoploss
            reward = target - buy_entry
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            return {
                'buy_entry': round(buy_entry, 2),
                'target': round(target, 2),
                'stoploss': round(stoploss, 2),
                'risk_reward_ratio': round(risk_reward_ratio, 2),
                'upside_potential': round(((target - current_ltp) / current_ltp) * 100, 2) if current_ltp else 0,
                'downside_risk': round(((current_ltp - stoploss) / current_ltp) * 100, 2) if current_ltp else 0
            }
            
        except Exception as e:
            print(f"   ❌ Error calculating trading levels: {e}")
            return None

    def get_option_chain_from_input(self, symbol, input_data):
        """Get option chain from the provided input data"""
        try:
            options_data = []
            
            # Filter options for the given symbol from input data
            for option in input_data.get('options', []):
                option_symbol = option.get('symbol', '')
                option_name = option.get('name', '')
                
                # Check if this option belongs to our stock symbol
                if symbol in option_symbol or symbol == option_name:
                    # Parse strike price correctly (divide by 100 as it's stored with 2 decimals)
                    strike_price = float(option.get('strike', 0)) / 100
                    
                    # Determine option type from symbol
                    option_type = 'CE' if 'CE' in option_symbol else 'PE'
                    
                    options_data.append({
                        'symbol': option_symbol,
                        'token': option.get('token'),
                        'strike': strike_price,
                        'type': option_type,
                        'expiry': option.get('expiry', ''),
                        'lotsize': option.get('lotsize', 1)
                    })
            
            print(f"   📊 Found {len(options_data)} options contracts for {symbol}")
            return options_data
            
        except Exception as e:
            print(f"   ❌ Error getting option chain from input: {e}")
            return None
        
    def filter_current_month_options(self, options):
        """
        Filter options to keep only current month expiry contracts
        More robust version using datetime parsing
        """
        try:
            current_date = datetime.now()
            current_month = current_date.month
            current_year = current_date.year
            
            current_month_options = []
            expiry_count = {}
            
            for option in options:
                expiry_str = option.get('expiry', '')
                
                try:
                    # Parse expiry string to datetime (format: '28OCT2025')
                    expiry_date = datetime.strptime(expiry_str, '%d%b%Y')
                    
                    # Count expiries for statistics
                    expiry_month_year = expiry_date.strftime('%b-%Y')
                    expiry_count[expiry_month_year] = expiry_count.get(expiry_month_year, 0) + 1
                    
                    # Check if expiry is in current month and year
                    if expiry_date.month == current_month and expiry_date.year == current_year:
                        current_month_options.append(option)
                        
                except ValueError:
                    print(f"⚠️  Could not parse expiry: {expiry_str}")
                    continue
            
            # Print expiry statistics
            print(f"   📅 Expiry distribution:")
            for expiry, count in expiry_count.items():
                status = "✅ CURRENT" if expiry == current_date.strftime('%b-%Y') else "📅 FUTURE"
                print(f"      {expiry}: {count} options {status}")
            
            print(f"   ✅ Current month options filtered: {len(current_month_options)}")
            return current_month_options
            
        except Exception as e:
            print(f"❌ Error in current month filtering: {e}")
            return options  # Return original list if error occurs


    def select_best_strikes(self, options_data, day_high):
        """Select best CE and PE strikes based on day high"""
        try:
            # Separate CE and PE options
            ce_options = [opt for opt in options_data if opt['type'] == 'CE']
            pe_options = [opt for opt in options_data if opt['type'] == 'PE']

            ce_options = self.filter_current_month_options(ce_options)
            pe_options = self.filter_current_month_options(pe_options)

            print(f"   📈 {len(ce_options)} CE options, {len(pe_options)} PE options found")
            print(f"   Stock Day High: ₹{day_high:,.2f}")
            
            # For CE: select strike just below day high
            valid_ce = [opt for opt in ce_options if opt['strike'] < day_high]
            if valid_ce:
                # Sort by proximity to day high (closest first)
                valid_ce.sort(key=lambda x: abs(x['strike'] - day_high))
                best_ce = valid_ce[0]  # Closest strike below day high
                print(f"   ✅ Best CE: ₹{best_ce['strike']:,.2f} (Difference: -₹{day_high - best_ce['strike']:,.2f})")
            else:
                best_ce = None
                print(f"   ❌ No CE strikes below day high")
            
            # For PE: select strike just above day high
            valid_pe = [opt for opt in pe_options if opt['strike'] > day_high]
            if valid_pe:
                # Sort by proximity to day high (closest first)
                valid_pe.sort(key=lambda x: abs(x['strike'] - day_high))
                best_pe = valid_pe[0]  # Closest strike above day high
                print(f"   ✅ Best PE: ₹{best_pe['strike']:,.2f} (Difference: +₹{best_pe['strike'] - day_high:,.2f})")
            else:
                best_pe = None
                print(f"   ❌ No PE strikes above day high")
            
            return best_ce, best_pe, valid_pe
            
        except Exception as e:
            print(f"   ❌ Error selecting best strikes: {e}")
            return None, None, []

    def analyze_stock_with_options(self, stock_data, input_data):
        """Complete analysis for a single stock"""
        symbol = stock_data.get('symbol', '').replace('-EQ', '')
        name = stock_data.get('name')
        token = stock_data.get('token')
        
        print(f"\n🔍 Analyzing {name} ({symbol}) - Token: {token}")
        print("=" * 60)
        
        # Add delay between API calls
        time.sleep(1)

        # Get historical OHLC data for stock
        historical_data = self.get_historical_data(token)
        
        if not historical_data:
            print(f"❌ Could not fetch OHLC data for {symbol}")
            return None
        
        day_open = historical_data['open']
        day_high = historical_data['high']
        day_low = historical_data['low']
        day_close = historical_data['close']
        volume = historical_data['volume']
        
        # Check if stock price is above ₹1000
        if day_close < self.min_price:
            print(f"❌ Stock price ₹{day_close:,.2f} is below ₹{self.min_price:,} filter")
            return None
        
        print(f"✅ Stock meets price filter: ₹{day_close:,.2f} > ₹{self.min_price:,}")
        
        print(f"📊 STOCK OHLC Data:")
        print(f"   Open:   ₹{day_open:,.2f}")
        print(f"   High:   ₹{day_high:,.2f}")
        print(f"   Low:    ₹{day_low:,.2f}") 
        print(f"   Close:  ₹{day_close:,.2f}")
        print(f"   Volume: {volume:,.0f}")
        
        # Get option chain from input data
        options = self.get_option_chain_from_input(symbol, input_data)
        
        if not options:
            print(f"❌ No options found for {symbol}")
            return None
        
        # Select best strikes based on day high
        best_ce, best_pe, pe_options = self.select_best_strikes(options, day_high)
        
        print(f"\n🎯 OPTION STRATEGY (Based on Stock Day High: ₹{day_high:,.2f})")
        print("-" * 50)
        
        result_data = {
            'stock': stock_data,
            'historical': historical_data,
            'options': {
                'ce': None,
                'pe': None
            }
        }
        
        # Analyze CE option
        if best_ce:
            print(f"🟢 CALL (CE) - Strike below Day High:")
            print(f"   Symbol:    {best_ce['symbol']}")
            print(f"   Strike:    ₹{best_ce['strike']:,.2f}")
            print(f"   Token:     {best_ce['token']}")
            print(f"   Expiry:    {best_ce['expiry']}")
            print(f"   Lot Size:  {best_ce['lotsize']}")
            print(f"   Difference: -₹{day_high - best_ce['strike']:,.2f} from Stock Day High")
            
            # Get LTP and OHLC for CE option
            ce_ltp = self.get_ltp_data(best_ce)
            ce_ohlc = self.get_option_day_high_low(best_ce)
            
            if ce_ltp:
                current_ltp = float(ce_ltp.get('ltp', 0))
                print(f"   LTP:       ₹{current_ltp:,.2f}")
                best_ce['ltp'] = current_ltp
            
            if ce_ohlc:
                print(f"   Option Day High:  ₹{ce_ohlc['day_high']:,.2f}")
                print(f"   Option Day Low:   ₹{ce_ohlc['day_low']:,.2f}")
                print(f"   Option Day Open:  ₹{ce_ohlc['day_open']:,.2f}")
                print(f"   Option Day Close: ₹{ce_ohlc['day_close']:,.2f}")
                best_ce['option_ohlc'] = ce_ohlc
                
                # Calculate trading levels for CE
                if ce_ohlc['day_high'] > 0:
                    trading_levels = self.calculate_trading_levels(ce_ohlc['day_high'], best_ce.get('ltp', 0))
                    if trading_levels:
                        print(f"\n   📊 TRADING STRATEGY FOR CE:")
                        print(f"   🟢 Buy Entry:    ₹{trading_levels['buy_entry']:,.2f} (Above Option Day High)")
                        print(f"   🎯 Target:       ₹{trading_levels['target']:,.2f} (+5% from Option Day High)")
                        print(f"   🛑 Stoploss:     ₹{trading_levels['stoploss']:,.2f} (-5% from Option Day High)")
                        print(f"   📈 Risk-Reward:  {trading_levels['risk_reward_ratio']}:1")
                        print(f"   📊 Upside:       +{trading_levels['upside_potential']}%")
                        print(f"   📉 Downside:     -{trading_levels['downside_risk']}%")
                        best_ce['trading_levels'] = trading_levels
            
            result_data['options']['ce'] = best_ce
        else:
            print(f"❌ No suitable CE strike found below Day High")
        
        # Analyze PE option
        if best_pe:
            print(f"\n🔴 PUT (PE) - Strike above Day High:")
            print(f"   Symbol:    {best_pe['symbol']}")
            print(f"   Strike:    ₹{best_pe['strike']:,.2f}")
            print(f"   Token:     {best_pe['token']}")
            print(f"   Expiry:    {best_pe['expiry']}")
            print(f"   Lot Size:  {best_pe['lotsize']}")
            print(f"   Difference: +₹{best_pe['strike'] - day_high:,.2f} from Stock Day High")
            
            # Get LTP and OHLC for PE option
            pe_ltp = self.get_ltp_data(best_pe)
            pe_ohlc = self.get_option_day_high_low(best_pe)
            
            if pe_ltp:
                current_ltp = float(pe_ltp.get('ltp', 0))
                print(f"   LTP:       ₹{current_ltp:,.2f}")
                best_pe['ltp'] = current_ltp
            
            if pe_ohlc:
                print(f"   Option Day High:  ₹{pe_ohlc['day_high']:,.2f}")
                print(f"   Option Day Low:   ₹{pe_ohlc['day_low']:,.2f}")
                print(f"   Option Day Open:  ₹{pe_ohlc['day_open']:,.2f}")
                print(f"   Option Day Close: ₹{pe_ohlc['day_close']:,.2f}")
                best_pe['option_ohlc'] = pe_ohlc
                
                # Calculate trading levels for PE
                if pe_ohlc['day_high'] > 0:
                    trading_levels = self.calculate_trading_levels(pe_ohlc['day_high'], best_pe.get('ltp', 0))
                    if trading_levels:
                        print(f"\n   📊 TRADING STRATEGY FOR PE:")
                        print(f"   🟢 Buy Entry:    ₹{trading_levels['buy_entry']:,.2f} (Above Option Day High)")
                        print(f"   🎯 Target:       ₹{trading_levels['target']:,.2f} (+5% from Option Day High)")
                        print(f"   🛑 Stoploss:     ₹{trading_levels['stoploss']:,.2f} (-5% from Option Day High)")
                        print(f"   📈 Risk-Reward:  {trading_levels['risk_reward_ratio']}:1")
                        print(f"   📊 Upside:       +{trading_levels['upside_potential']}%")
                        print(f"   📉 Downside:     -{trading_levels['downside_risk']}%")
                        best_pe['trading_levels'] = trading_levels
            
            result_data['options']['pe'] = best_pe
            
            # Show alternative PE strikes
            if len(pe_options) > 1:
                print(f"\n📋 Alternative PE Strikes:")
                for i, pe in enumerate(pe_options[1:4], 2):  # Show next 3 strikes
                    print(f"   {i}. Strike: ₹{pe['strike']:,.2f} (+₹{pe['strike'] - day_high:,.2f}) - {pe['symbol']}")
        else:
            print(f"❌ No suitable PE strike found above Day High")
        
        return result_data
    
    def process_stocks_list(self, input_data):
        """Process list of stocks from input data"""
        # if not self.create_session():
        #     return None
        
        print("🎯 PROCESSING STOCKS > ₹1000")
        print("=" * 80)
        
        # Get stocks from input data
        stocks_list = input_data.get('stocks', [])
        
        print(f"📈 Found {len(stocks_list)} stocks to analyze")
        
        results = []
        stocks_above_1000 = 0
        
        for stock in stocks_list:
            analysis_result = self.analyze_stock_with_options(stock, input_data)
            if analysis_result:
                results.append(analysis_result)
                stocks_above_1000 += 1
            
            # Add delay between stock analysis
            time.sleep(2)
        
        print(f"\n✅ Analysis Complete: {stocks_above_1000}/{len(stocks_list)} stocks above ₹{self.min_price:,}")
        return results
    
    def get_ltp_data(self, option_data):
        """Get last traded price for options"""
        try:
            if not option_data or 'token' not in option_data:
                print(f"   ❌ Invalid option data for LTP")
                return None
                
            ltp_data = self.smart_api.ltpData(
                exchange="NFO",
                tradingsymbol=option_data['symbol'],
                symboltoken=option_data['token']
            )
            
            if ltp_data and 'status' in ltp_data and ltp_data['status']:
                return ltp_data['data']
            else:
                print(f"   ❌ LTP data error for {option_data['symbol']}")
                return None
                
        except Exception as e:
            print(f"   ❌ Error fetching LTP data for {option_data['symbol']}: {e}")
            return None


    # Example usage
    def run(self):
        # Your input data
        input_payload = "( {33489} ( daily high < 1 day ago high and daily low > 1 day ago low and daily close > daily open and daily close > 1000 and daily close > daily open and 1 day ago close < 1 day ago open and daily close > daily open and 1 day ago close < 1 day ago open ) ) "

        # Fetch data (using your provided data structure)
        stocks_data = fetch_chartink_data(input_payload)

        stock_details = get_stock_details(stocks_data)

        # analyzer = StockAnalysis()
        results = self.process_stocks_list(stock_details)
        
        # Save results to JSON
        if results:
            timestamp = datetime.now().strftime("%A_%Y-%m-%d")
            filename = f"stock_interaday_json/stock_interaday_analysis_{timestamp}.json"
            
            output_data = {
                'analysis_time': datetime.now().isoformat(),
                'min_price_filter': self.min_price,
                'stocks_analyzed': len(results),
                'results': results
            }
            
            with open(filename, 'w') as f:
                json.dump(output_data, f, indent=4)

            message=""
            
            print(f"\n💾 Analysis saved to: {filename}")
            
            # Print summary
            print(f"\n📊 STOCK OPTIONS TRADING STRATEGY SUMMARY")
            message+=f"\n *📊 STOCK OPTIONS TRADING STRATEGY SUMMARY* \n"
            print("=" * 80)
            for result in results:
                stock = result['stock']
                historical = result['historical']
                options = result['options']
                
                print(f"\n📈 {stock['name']} ({stock['symbol']})")
                message+=f"\n📈 *{stock['name']} ({stock['symbol']})*\n"
                print(f"   Stock Price: ₹{historical['close']:,.2f} | Stock Day High: ₹{historical['high']:,.2f}")
                message+=f"   *Stock Price:* ₹{historical['close']:,.2f} | *Stock Day High:* ₹{historical['high']:,.2f}\n"
                
                if options['ce']:
                    ce = options['ce']
                    trading_levels = ce.get('trading_levels', {})
                    print(f"   🟢 CE: {ce['symbol']}")
                    message+=f"\n🟢 *CE:* {ce['symbol']}\n"
                    print(f"      Strike: ₹{ce['strike']:,.2f} | LTP: ₹{ce.get('ltp', 'N/A')}")
                    message+=f"      *Strike:* ₹{ce['strike']:,.2f} | *LTP:* ₹{ce.get('ltp', 'N/A')}\n"
                    print(f"      Entry: ₹{trading_levels.get('buy_entry', 'N/A')} | Target: ₹{trading_levels.get('target', 'N/A')}")
                    message+=f"      *Entry:* ₹{trading_levels.get('buy_entry', 'N/A')} | *Target:* ₹{trading_levels.get('target', 'N/A')}\n"
                    print(f"      Stoploss: ₹{trading_levels.get('stoploss', 'N/A')} | R:R: {trading_levels.get('risk_reward_ratio', 'N/A')}:1")
                    message+=f"      *Stoploss:* ₹{trading_levels.get('stoploss', 'N/A')} | *R:R:* {trading_levels.get('risk_reward_ratio', 'N/A')}:1\n"
                
                if options['pe']:
                    pe = options['pe']
                    trading_levels = pe.get('trading_levels', {})
                    print(f"   🔴 PE: {pe['symbol']}")
                    message+=f"\n🔴 *PE:* {pe['symbol']}\n"
                    print(f"      Strike: ₹{pe['strike']:,.2f} | LTP: ₹{pe.get('ltp', 'N/A')}")
                    message+=f"      *Strike:* ₹{pe['strike']:,.2f} | *LTP:* ₹{pe.get('ltp', 'N/A')}\n"
                    print(f"      Entry: ₹{trading_levels.get('buy_entry', 'N/A')} | Target: ₹{trading_levels.get('target', 'N/A')}")
                    message+=f"      *Entry:* ₹{trading_levels.get('buy_entry', 'N/A')} | *Target:* ₹{trading_levels.get('target', 'N/A')}\n"
                    print(f"      Stoploss: ₹{trading_levels.get('stoploss', 'N/A')} | R:R: {trading_levels.get('risk_reward_ratio', 'N/A')}:1")
                    message+=f"      *Stoploss:* ₹{trading_levels.get('stoploss', 'N/A')} | *R:R:* {trading_levels.get('risk_reward_ratio', 'N/A')}:1\n"
           
        else:
            print("❌ No stocks found above ₹1000 or analysis failed")

        send_telegram_message(message)
        
# from src.main.interaday_stock_options.angel_one.stock_options_analysis import UpdateStockOptData
# analyzer = UpdateStockOptData()
# analyzer.run()