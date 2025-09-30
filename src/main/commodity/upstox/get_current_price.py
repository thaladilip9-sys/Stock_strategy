import upstox_client
from dotenv import load_dotenv
import os
from src.utils.send_message import send_whatsapp_message,send_telegram_message
from src.main.commodity.get_contract_data import smart_mcx_contracts
from datetime import datetime
import time
import json

load_dotenv('./env/.env.prod')
ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD_COMMODITY", 300))

class BeautifulWebSocketMonitor:
    def __init__(self,  symbol_data):
        self.instrument_key = symbol_data.get('instrument_key')
        self.symbol_data = symbol_data
        self.configuration = upstox_client.Configuration()
        self.configuration.access_token = ACCESS_TOKEN
        self.streamer = upstox_client.MarketDataStreamerV3(upstox_client.ApiClient(self.configuration))
        self.last_alert_time = None
        self.alert_cooldown = 300  # 5 minutes cooldown between same alerts
        
    def create_beautiful_alert_message(self, alert_type, current_price, timestamp):
        """Create beautifully formatted alert message"""
        
        symbol_name = self.symbol_data.get('trading_symbol', 'Unknown')
        base_symbol = symbol_name.split()[0] if symbol_name else 'Unknown'
        
        if alert_type == "BUY":
            return self._create_buy_alert(base_symbol, current_price, timestamp)
        else:
            return self._create_sell_alert(base_symbol, current_price, timestamp)
    
    def _create_buy_alert(self, symbol_name, current_price, timestamp):
        """Create beautiful buy alert"""
        buy_entry = self.symbol_data.get('buy_entry', 0)
        buy_target = self.symbol_data.get('buy_target', 0)
        buy_sl = self.symbol_data.get('buy_sl', 0)
        
        return f"""🎯 *BUY SIGNAL TRIGGERED* 🎯

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💎 *SYMBOL:* {symbol_name}
📊 *CONTRACT:* {self.symbol_data.get('trading_symbol', 'N/A')}
💰 *CURRENT PRICE:* ₹{current_price:,.2f}

📈 *ENTRY LEVEL REACHED*
   ┌─────────────────────────────┐
   │ Current Price: ₹{current_price:>10,.2f} │
   │ Buy Entry:    ₹{buy_entry:>10,.2f} │
   │ Difference:    ₹{abs(current_price - buy_entry):>9.2f} │
   └─────────────────────────────┘

🟢 *TRADING ACTION*
   • Execute BUY Order
   • Entry Price: ₹{buy_entry:,.2f}
   • Target: ₹{buy_target:,.2f} (+{(buy_target/buy_entry-1)*100:.1f}%)
   • Stop Loss: ₹{buy_sl:,.2f} ({(buy_sl/buy_entry-1)*100:.1f}%)

⚡ *RISK MANAGEMENT*
   • Position Size: 1-2% of capital
   • Risk-Reward: 1:1.5
   • Use strict stop loss

⏰ *TIME:* {timestamp}
🔗 *SOURCE:* Real-time WebSocket

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 *Automated Trading Alert*
   Trade responsibly. Always use stop loss."""

    def _create_sell_alert(self, symbol_name, current_price, timestamp):
        """Create beautiful sell alert"""
        sell_entry = self.symbol_data.get('sell_entry', 0)
        sell_target = self.symbol_data.get('sell_target', 0)
        sell_sl = self.symbol_data.get('sell_sl', 0)
        
        return f"""🎯 *SELL SIGNAL TRIGGERED* 🎯

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💎 *SYMBOL:* {symbol_name}
📊 *CONTRACT:* {self.symbol_data.get('trading_symbol', 'N/A')}
💰 *CURRENT PRICE:* ₹{current_price:,.2f}

📉 *ENTRY LEVEL REACHED*
   ┌─────────────────────────────┐
   │ Current Price: ₹{current_price:>10,.2f} │
   │ Sell Entry:   ₹{sell_entry:>10,.2f} │
   │ Difference:    ₹{abs(current_price - sell_entry):>9.2f} │
   └─────────────────────────────┘

🔴 *TRADING ACTION*
   • Execute SELL Order
   • Entry Price: ₹{sell_entry:,.2f}
   • Target: ₹{sell_target:,.2f} ({(sell_target/sell_entry-1)*100:.1f}%)
   • Stop Loss: ₹{sell_sl:,.2f} ({(sell_sl/sell_entry-1)*100:.1f}%)

⚡ *RISK MANAGEMENT*
   • Position Size: 1-2% of capital
   • Risk-Reward: 1:1.5
   • Use strict stop loss

⏰ *TIME:* {timestamp}
🔗 *SOURCE:* Real-time WebSocket

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 *Automated Trading Alert*
   Trade responsibly. Always use stop loss."""

    def on_open(self):
        """WebSocket connection opened"""
        print("✅ Connected to live market feed")
        print(f"📡 Subscribing to: {self.instrument_key}")
        self.streamer.subscribe([self.instrument_key], "full")

    def on_message(self, msg):
        """Handle incoming WebSocket messages"""
        try:
            ltp = msg.get("ltp")
            symbol = msg.get("symbol", "Unknown")
            ts = msg.get("exchange_ts", datetime.now().isoformat())
            
            if ltp is not None:
                buy_entry = self.symbol_data.get('buy_entry', 0)
                sell_entry = self.symbol_data.get('sell_entry', 0)
                
                # Format timestamp for display
                display_ts = datetime.fromisoformat(ts.replace('Z', '+00:00')).strftime('%H:%M:%S')
                
                print(f"📊 {symbol} | LTP: ₹{ltp:,.2f} | Time: {display_ts} | Buy: ₹{buy_entry:,.2f} | Sell: ₹{sell_entry:,.2f}")
                
                # Check buy condition
                if abs(ltp - buy_entry) <= ALERT_THRESHOLD:
                    self.handle_alert("BUY", ltp, ts, buy_entry)
                
                # Check sell condition
                elif abs(ltp - sell_entry) <= ALERT_THRESHOLD:
                    self.handle_alert("SELL", ltp, ts, sell_entry)
                    
        except Exception as e:
            print(f"❌ Error processing message: {e}")

    def handle_alert(self, alert_type, current_price, timestamp, entry_price):
        """Handle alert triggering with cooldown"""
        current_time = time.time()
        
        # Check cooldown period
        if self.last_alert_time and (current_time - self.last_alert_time) < self.alert_cooldown:
            print(f"⏳ Alert cooldown active for {alert_type}")
            return
        
        # Create beautiful message
        alert_message = self.create_beautiful_alert_message(alert_type, current_price, timestamp)
        
        # Send WhatsApp message
        try:
            send_telegram_message(alert_message)
            print(f"✅ {alert_type} alert sent successfully!")
            self.last_alert_time = current_time
            
            # Log the alert
            self.log_alert(alert_type, current_price, entry_price, timestamp)
            
        except Exception as e:
            print(f"❌ Failed to send {alert_type} alert: {e}")

    def log_alert(self, alert_type, current_price, entry_price, timestamp):
        """Log alert to file"""
        log_entry = {
            "timestamp": timestamp,
            "alert_type": alert_type,
            "symbol": self.symbol_data.get('trading_symbol'),
            "current_price": current_price,
            "entry_price": entry_price,
            "difference": abs(current_price - entry_price)
        }
        
        try:
            with open('trading_alerts.log', 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except:
            pass  # Silent fail for logging

    def on_error(self, error):
        """WebSocket error handler"""
        print(f"❌ WebSocket error: {error}")

    def on_close(self):
        """WebSocket connection closed"""
        print("🔌 WebSocket connection closed")

    def start_monitoring(self):
        """Start the WebSocket monitoring"""
        print(f"🚀 Starting WebSocket Monitor for {self.symbol_data.get('trading_symbol')}")
        print("=" * 60)
        
        # Set up event handlers
        self.streamer.on("open", self.on_open)
        self.streamer.on("message", self.on_message)
        self.streamer.on("error", self.on_error)
        self.streamer.on("close", self.on_close)
        
        try:
            self.streamer.connect()
            
            # Keep the connection alive
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
        except Exception as e:
            print(f"❌ Monitoring error: {e}")

def main(data):
    """Main function to start monitoring"""
    monitor = BeautifulWebSocketMonitor(data)
    monitor.start_monitoring()


if __name__ == "__main__":  # Example usage
    goldm_data, silverm_data = smart_mcx_contracts()

    main(goldm_data)