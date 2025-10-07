# live_option_monitor.py

import json
import time
import requests
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import pyotp
import threading
from typing import Dict, List, Optional
import logging
import asyncio
import concurrent.futures
from queue import Queue, Empty
import multiprocessing
from collections import defaultdict
from src.utils.angel_one_connect import AngelOneConnect
from src.utils.send_message import send_telegram_message, send_telegram_message_admin

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('option_monitor.log'),
        logging.StreamHandler()
    ]
)

load_dotenv('./env/.env.prod')

class ParallelOptionMonitor:
    def __init__(self):
        self.smart_api = None
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.monitored_options = []
        
        # Enhanced tracking sets with mutual exclusion
        self.alerted_targets = set()  # Options that hit target
        self.alerted_stoploss = set()  # Options that hit stoploss
        self.alerted_entries = set()  # Options that triggered entry
        self.entered_positions = set()  # Track positions that have been entered
        self.completed_positions = set()  # Track positions that are completed (target or stoploss hit)
        
        self.last_ltp = {}  # Store last LTP for change detection
        self.is_ws_connected = False
        self.ws_thread = None
        self.web_socket = None
        self.token_map = {}  # Map tokens to option data
        self.correlation_id = "option_monitor_001"
        self.max_ws_tokens = 3000
        
        # Parallel processing attributes
        self.alert_queue = Queue()
        self.alert_threads = []
        self.max_alert_workers = 5
        self.data_queue = Queue()
        self.is_running = True
        
        # Performance tracking
        self.message_count = 0
        self.last_alert_time = defaultdict(float)
        self.alert_cooldown = 2  # seconds between same option alerts

        # Enhanced Memory Context
        self.monitoring_context = {
            'session_start_time': datetime.now().isoformat(),
            'total_alerts_sent': 0,
            'alerts_by_type': {'entry': 0, 'target': 0, 'stoploss': 0},
            'options_loaded': 0,
            'gap_up_skipped': 0,
            'webSocket_reconnects': 0,
            'last_health_report': None,
            'performance_metrics': {
                'avg_alert_processing_time': 0,
                'max_queue_size': 0,
                'total_data_points': 0
            },
            'trading_session': {
                'start_time': datetime.now().isoformat(),
                'market_status': 'UNKNOWN',
                'last_sync_time': None
            },
            'position_management': {
                'active_positions': 0,
                'completed_positions': 0,
                'profitable_exits': 0,
                'loss_exits': 0
            }
        }

        self.connect_object = AngelOneConnect()
        self.smart_api = self.connect_object.connect()

    def update_context(self, key, value, subkey=None):
        """Update monitoring context with new data"""
        try:
            if subkey:
                if key not in self.monitoring_context:
                    self.monitoring_context[key] = {}
                self.monitoring_context[key][subkey] = value
            else:
                self.monitoring_context[key] = value
        except Exception as e:
            logging.error(f"Error updating context: {e}")

    def get_context_summary(self):
        """Get a summary of the current monitoring context"""
        return {
            'session_duration': str(datetime.now() - datetime.fromisoformat(self.monitoring_context['session_start_time'])),
            'total_options_monitored': len(self.monitored_options),
            'active_positions': len(self.entered_positions),
            'completed_positions': len(self.completed_positions),
            'alerts_sent': self.monitoring_context['total_alerts_sent'],
            'alerts_breakdown': self.monitoring_context['alerts_by_type'],
            'system_health': {
                'webSocket_connected': self.is_ws_connected,
                'alert_workers_active': len([t for t in self.alert_threads if t.is_alive()]),
                'current_queue_size': self.alert_queue.qsize(),
                'memory_usage': len(self.token_map)
            }
        }

    def is_position_active(self, unique_id: str) -> bool:
        """Check if position is still active (not completed)"""
        return unique_id in self.entered_positions and unique_id not in self.completed_positions

    def mark_position_completed(self, unique_id: str, exit_type: str):
        """Mark a position as completed and update context"""
        if unique_id in self.entered_positions:
            self.completed_positions.add(unique_id)
            
            # Update context
            self.update_context('completed_positions', len(self.completed_positions), 'position_management')
            self.update_context('active_positions', len(self.entered_positions) - len(self.completed_positions), 'position_management')
            
            if exit_type == 'target':
                self.update_context('profitable_exits', 
                                  self.monitoring_context['position_management']['profitable_exits'] + 1, 
                                  'position_management')
                logging.info(f"✅ Position {unique_id} completed with TARGET (Profit)")
            elif exit_type == 'stoploss':
                self.update_context('loss_exits', 
                                  self.monitoring_context['position_management']['loss_exits'] + 1, 
                                  'position_management')
                logging.info(f"🛑 Position {unique_id} completed with STOPLOSS (Loss)")

    def load_analysis_data(self, json_file_path: str):
        """Load analysis data from JSON file"""
        try:
            with open(json_file_path, 'r') as f:
                data = json.load(f)
            
            logging.info(f"Loaded analysis data from: {json_file_path}")
            logging.info(f"Analysis Time: {data.get('analysis_time', 'N/A')}")
            logging.info(f"Stocks Analyzed: {data.get('stocks_analyzed', 0)}")
            
            # Extract options to monitor
            self.monitored_options = []
            self.token_map = {}
            valid_tokens = 0
            skipped_gap_up = 0
            
            for result in data.get('results', []):
                stock = result.get('stock', {})
                options_data = result.get('options', {})
                
                # Monitor CE options
                if options_data.get('ce'):
                    ce_option = options_data['ce']
                    token = ce_option.get('token')
                    
                    if token and str(token).strip():
                        # Check for gap up condition
                        day_open = ce_option.get('option_ohlc', {}).get('day_open', 0)
                        buy_entry = ce_option.get('trading_levels', {}).get('buy_entry', 0)
                        
                        if day_open > buy_entry:
                            logging.info(f"⏩ Skipping {ce_option.get('symbol')} - Gap up detected (Open: {day_open} > Entry: {buy_entry})")
                            skipped_gap_up += 1
                            continue
                        
                        ce_option['stock_name'] = stock.get('name')
                        ce_option['stock_symbol'] = stock.get('symbol')
                        ce_option['stock_day_high'] = result.get('historical', {}).get('high', 0)
                        ce_option['option_type'] = 'CE'
                        ce_option['unique_id'] = f"{ce_option['symbol']}_{ce_option['option_type']}"
                        ce_option['alert_key'] = f"{ce_option['symbol']}_{ce_option['option_type']}"
                        ce_option['loaded_time'] = datetime.now().isoformat()
                        self.monitored_options.append(ce_option)
                        
                        # Add to token map for WebSocket
                        self.token_map[token] = ce_option
                        valid_tokens += 1
                
                # Monitor PE options
                if options_data.get('pe'):
                    pe_option = options_data['pe']
                    token = pe_option.get('token')
                    
                    if token and str(token).strip():
                        # Check for gap up condition
                        day_open = pe_option.get('option_ohlc', {}).get('day_open', 0)
                        buy_entry = pe_option.get('trading_levels', {}).get('buy_entry', 0)
                        
                        if day_open > buy_entry:
                            logging.info(f"⏩ Skipping {pe_option.get('symbol')} - Gap up detected (Open: {day_open} > Entry: {buy_entry})")
                            skipped_gap_up += 1
                            continue
                        
                        pe_option['stock_name'] = stock.get('name')
                        pe_option['stock_symbol'] = stock.get('symbol')
                        pe_option['stock_day_high'] = result.get('historical', {}).get('high', 0)
                        pe_option['option_type'] = 'PE'
                        pe_option['unique_id'] = f"{pe_option['symbol']}_{pe_option['option_type']}"
                        pe_option['alert_key'] = f"{pe_option['symbol']}_{pe_option['option_type']}"
                        pe_option['loaded_time'] = datetime.now().isoformat()
                        self.monitored_options.append(pe_option)
                        
                        # Add to token map for WebSocket
                        self.token_map[token] = pe_option
                        valid_tokens += 1
            
            # Update context with loading statistics
            self.update_context('options_loaded', len(self.monitored_options))
            self.update_context('gap_up_skipped', skipped_gap_up)
            self.update_context('valid_tokens', valid_tokens)
            
            logging.info(f"Monitoring {len(self.monitored_options)} options")
            logging.info(f"Skipped {skipped_gap_up} options due to gap up")
            logging.info(f"Valid tokens: {valid_tokens}")
            
            # Initialize last LTP storage
            for option in self.monitored_options:
                self.last_ltp[option['unique_id']] = 0
                
            return True
            
        except Exception as e:
            logging.error(f"Error loading analysis data: {e}")
            return False

    def start_alert_workers(self):
        """Start parallel alert worker threads"""
        for i in range(self.max_alert_workers):
            thread = threading.Thread(
                target=self.alert_worker,
                name=f"AlertWorker-{i}",
                daemon=True
            )
            thread.start()
            self.alert_threads.append(thread)
            logging.info(f"Started alert worker thread {i+1}")

    def alert_worker(self):
        """Worker thread to process alerts in parallel"""
        while self.is_running:
            try:
                # Get alert from queue with timeout
                alert_data = self.alert_queue.get(timeout=1)
                if alert_data is None:
                    break
                    
                alert_type = alert_data['type']
                option_data = alert_data['option_data']
                current_ltp = alert_data['current_ltp']
                
                # Track alert processing start time
                processing_start = time.time()
                
                # Process alert based on type
                if alert_type == 'entry':
                    self.send_entry_alert(option_data, current_ltp)
                elif alert_type == 'target':
                    self.send_target_alert(option_data, current_ltp)
                elif alert_type == 'stoploss':
                    self.send_stoploss_alert(option_data, current_ltp)
                
                # Update context with alert metrics
                processing_time = time.time() - processing_start
                self.update_context('total_alerts_sent', self.monitoring_context['total_alerts_sent'] + 1)
                self.update_context('alerts_by_type', self.monitoring_context['alerts_by_type'][alert_type] + 1, alert_type)
                
                # Update performance metrics
                current_avg = self.monitoring_context['performance_metrics']['avg_alert_processing_time']
                total_alerts = self.monitoring_context['total_alerts_sent']
                new_avg = ((current_avg * (total_alerts - 1)) + processing_time) / total_alerts
                self.update_context('avg_alert_processing_time', new_avg, 'performance_metrics')
                
                self.alert_queue.task_done()
                
            except Empty:
                continue
            except Exception as e:
                logging.error(f"Error in alert worker: {e}")

    def send_entry_alert(self, option_data: Dict, current_ltp: float):
        """Send entry alert in parallel"""
        unique_id = option_data.get('unique_id')
        option_symbol = option_data.get('symbol')
        stock_name = option_data.get('stock_name')
        option_type = option_data.get('option_type')
        trading_levels = option_data.get('trading_levels', {})
        
        buy_entry = trading_levels.get('buy_entry', 0)
        target = trading_levels.get('target', 0)
        stoploss = trading_levels.get('stoploss', 0)
        
        message = f"""
*BUY ENTRY TRIGGERED*

*Stock:* {stock_name}
*Option:* {option_symbol}
*Type:* {option_type}
*Current LTP:* ₹{current_ltp:,.2f}
*Entry Level:* ₹{buy_entry:,.2f}

*Action:* BUY
*Target:* ₹{target:,.2f}
*Stop Loss:* ₹{stoploss:,.2f}

*Upside:* +{trading_levels.get('upside_potential', 0)}%
*Downside:* -{trading_levels.get('downside_risk', 0)}%
*Risk-Reward:* {trading_levels.get('risk_reward_ratio', 0)}:1

*{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
        """
        
        if send_telegram_message(message):
            self.alerted_entries.add(unique_id)
            self.entered_positions.add(unique_id)
            
            # Update context with position entry
            self.update_context('trading_session', {
                **self.monitoring_context['trading_session'],
                'last_entry_time': datetime.now().isoformat(),
                'active_positions_count': len(self.entered_positions)
            })
            self.update_context('active_positions', len(self.entered_positions), 'position_management')
            
            logging.info(f"PARALLEL Entry alert sent for {option_symbol}")

    def send_target_alert(self, option_data: Dict, current_ltp: float):
        """Send target alert in parallel"""
        unique_id = option_data.get('unique_id')
        option_symbol = option_data.get('symbol')
        stock_name = option_data.get('stock_name')
        option_type = option_data.get('option_type')
        trading_levels = option_data.get('trading_levels', {})
        
        buy_entry = trading_levels.get('buy_entry', 0)
        target = trading_levels.get('target', 0)
        profit_percentage = ((current_ltp - buy_entry) / buy_entry) * 100 if buy_entry > 0 else 0
        
        message = f"""
*TARGET ACHIEVED*

*Stock:* {stock_name}
*Option:* {option_symbol}
*Type:* {option_type}
*Current LTP:* ₹{current_ltp:,.2f}
*Target:* ₹{target:,.2f}

*Profit:* +{profit_percentage:.2f}%
*Entry was:* ₹{buy_entry:,.2f}

*Action:* BOOK PROFITS

*{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
        """
        
        if send_telegram_message(message):
            self.alerted_targets.add(unique_id)
            # Mark position as completed when target is hit
            self.mark_position_completed(unique_id, 'target')
            logging.info(f"PARALLEL Target hit for {option_symbol}")

    def send_stoploss_alert(self, option_data: Dict, current_ltp: float):
        """Send stoploss alert in parallel"""
        unique_id = option_data.get('unique_id')
        option_symbol = option_data.get('symbol')
        stock_name = option_data.get('stock_name')
        option_type = option_data.get('option_type')
        trading_levels = option_data.get('trading_levels', {})
        
        buy_entry = trading_levels.get('buy_entry', 0)
        stoploss = trading_levels.get('stoploss', 0)
        loss_percentage = ((buy_entry - current_ltp) / buy_entry) * 100 if buy_entry > 0 else 0
        
        message = f"""
*STOPLOSS HIT*

*Stock:* {stock_name}
*Option:* {option_symbol}
*Type:* {option_type}
*Current LTP:* ₹{current_ltp:,.2f}
*Stop Loss:* ₹{stoploss:,.2f}

*Loss:* -{loss_percentage:.2f}%
*Entry was:* ₹{buy_entry:,.2f}

*Action:* EXIT TRADE

*{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
        """
        
        if send_telegram_message(message):
            self.alerted_stoploss.add(unique_id)
            # Mark position as completed when stoploss is hit
            self.mark_position_completed(unique_id, 'stoploss')
            logging.info(f"PARALLEL Stoploss hit for {option_symbol}")

    def on_data(self, wsapp, message):
        """Callback function for WebSocket data - PARALLEL PROCESSING"""
        try:
            # Update data points counter
            self.update_context('total_data_points', 
                              self.monitoring_context['performance_metrics']['total_data_points'] + 1,
                              'performance_metrics')
            
            if 'token' in message:
                # Extract token from message
                full_token = message['token']
                token_parts = full_token.split('|')
                token = token_parts[1] if len(token_parts) > 1 else full_token
                
                raw_ltp = float(message['last_traded_price'])
                actual_ltp = raw_ltp / 100.0
                
                # Find the option using token map
                option_data = self.token_map.get(token)
                if option_data:
                    unique_id = option_data['unique_id']
                    previous_ltp = self.last_ltp.get(unique_id, 0)
                    
                    # Update last LTP
                    self.last_ltp[unique_id] = actual_ltp
                    
                    # Check trading levels in parallel
                    self.check_trading_levels_parallel(option_data, actual_ltp)
                    
                    # Log significant changes
                    if abs(actual_ltp - previous_ltp) > 0.1:
                        logging.debug(f"{option_data['stock_name']} {option_data['option_type']} | LTP: ₹{actual_ltp:,.2f}")
                    
        except Exception as e:
            logging.error(f"Error processing WebSocket data: {e}")

    def check_trading_levels_parallel(self, option_data: Dict, current_ltp: float):
        """Check trading levels and queue alerts for parallel processing"""
        unique_id = option_data.get('unique_id')
        trading_levels = option_data.get('trading_levels', {})
        
        if not trading_levels:
            return
        
        buy_entry = trading_levels.get('buy_entry', 0)
        target = trading_levels.get('target', 0)
        stoploss = trading_levels.get('stoploss', 0)
        alert_key = option_data.get('alert_key')
        
        # Check cooldown period
        current_time = time.time()
        if current_time - self.last_alert_time.get(alert_key, 0) < self.alert_cooldown:
            return
        
        # Check for BUY ENTRY trigger
        if (current_ltp >= buy_entry and 
            unique_id not in self.alerted_entries and
            unique_id not in self.completed_positions):  # Don't trigger entry if already completed
            
            alert_data = {
                'type': 'entry',
                'option_data': option_data,
                'current_ltp': current_ltp,
                'timestamp': datetime.now().isoformat()
            }
            self.alert_queue.put(alert_data)
            self.last_alert_time[alert_key] = current_time
            
            # Update queue size metrics
            current_queue_size = self.alert_queue.qsize()
            max_queue_size = self.monitoring_context['performance_metrics']['max_queue_size']
            if current_queue_size > max_queue_size:
                self.update_context('max_queue_size', current_queue_size, 'performance_metrics')
        
        # Only check target and stoploss if position was entered AND not completed
        elif (unique_id in self.entered_positions and 
              unique_id not in self.completed_positions):  # Check if position is still active
            
            # MUTUAL EXCLUSION LOGIC: Check if position is already completed
            if unique_id in self.completed_positions:
                return  # Position already completed, no further checks
            
            # Check for TARGET hit (only if position is active and not completed)
            if (current_ltp >= target and 
                unique_id not in self.alerted_targets and
                unique_id not in self.alerted_stoploss):  # Don't trigger target if stoploss already hit
                
                alert_data = {
                    'type': 'target',
                    'option_data': option_data,
                    'current_ltp': current_ltp,
                    'timestamp': datetime.now().isoformat()
                }
                self.alert_queue.put(alert_data)
                self.last_alert_time[alert_key] = current_time
            
            # Check for STOPLOSS hit (only if position is active and not completed)
            elif (current_ltp <= stoploss and 
                  unique_id not in self.alerted_stoploss and
                  unique_id not in self.alerted_targets):  # Don't trigger stoploss if target already hit
                
                alert_data = {
                    'type': 'stoploss',
                    'option_data': option_data,
                    'current_ltp': current_ltp,
                    'timestamp': datetime.now().isoformat()
                }
                self.alert_queue.put(alert_data)
                self.last_alert_time[alert_key] = current_time

    def on_open(self, wsapp):
        """Callback function for WebSocket open"""
        logging.info("WebSocket connection opened successfully")
        self.is_ws_connected = True
        
        # Update context with connection info
        self.update_context('webSocket_reconnects', 
                          self.monitoring_context['webSocket_reconnects'] + 1)
        self.update_context('trading_session', {
            **self.monitoring_context['trading_session'],
            'last_sync_time': datetime.now().isoformat(),
            'market_status': 'CONNECTED'
        })
        
        # Start alert workers when WebSocket connects
        self.start_alert_workers()
        
        connection_msg = f"""
*PARALLEL MONITORING STARTED*

*Monitoring Status:* ACTIVE
*Options Tracked:* {len(self.monitored_options)}/{len(self.monitored_options)}
*Alert Workers:* {self.max_alert_workers}
*Queue Size:* {self.alert_queue.qsize()}
*Messages Sent:* {self.message_count}

*Alerts Triggered:*
   • Entries: {len(self.alerted_entries)}
   • Targets: {len(self.alerted_targets)}
   • Stoploss: {len(self.alerted_stoploss)}

*Active Positions:* {len(self.entered_positions)}

*Report Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

*All systems running in parallel*
"""
        send_telegram_message_admin(connection_msg)

    def on_error(self, wsapp, error):
        """Callback function for WebSocket error"""
        logging.error(f"WebSocket error: {error}")
        self.is_ws_connected = False
        self.update_context('trading_session', {
            **self.monitoring_context['trading_session'],
            'market_status': 'DISCONNECTED'
        })

    def on_close(self, wsapp):
        """Callback function for WebSocket close"""
        logging.warning("WebSocket connection closed")
        self.is_ws_connected = False
        self.update_context('trading_session', {
            **self.monitoring_context['trading_session'],
            'market_status': 'CLOSED'
        })

    def start_websocket_monitoring(self):
        """Start WebSocket V2 monitoring for real-time data"""
        try:
            # Get feed token and other required parameters
            feed_token = self.connect_object.smart_api.getfeedToken()
            
            if not feed_token:
                logging.error("Could not get feed token for WebSocket")
                return False
            
            client_code = os.getenv("ANGEL_CLIENT_ID")
            jwt_token = self.connect_object.session_data['data']['jwtToken']
            

            if not jwt_token:
                logging.error("Could not get JWT token")
                return False
            
            # Prepare token list in EXACT format expected by SmartAPI
            nfo_tokens = []
            for token in self.token_map.keys():
                # Just collect the numeric tokens
                nfo_tokens.append(str(token))
                
                if len(nfo_tokens) >= self.max_ws_tokens:
                    logging.warning(f"Reached maximum token limit ({self.max_ws_tokens})")
                    break
            
            # Format for SmartWebSocketV2
            token_list = [
                {
                    "exchangeType": 2,  # 2 = NFO, 1 = NSE, 13 = BSE
                    "tokens": nfo_tokens
                }
            ]
            
            logging.info(f"Subscribing to {len(nfo_tokens)} NFO tokens via WebSocket")
            
            # WebSocket configuration
            sws = SmartWebSocketV2(
                auth_token=jwt_token,
                api_key=os.getenv("ANGEL_API_KEY"),
                client_code=client_code,
                feed_token=feed_token
            )
            
            self.web_socket = sws
            
            # Assign callbacks
            sws.on_open = self.on_open
            sws.on_data = self.on_data
            sws.on_error = self.on_error
            sws.on_close = self.on_close
            
            # Start WebSocket thread
            self.ws_thread = threading.Thread(
                target=sws.connect,
                daemon=True
            )
            
            self.ws_thread.start()
            
            # Wait for connection to establish
            time.sleep(3)
            
            # Subscribe with proper parameters
            if self.is_ws_connected:
                try:
                    # SmartWebSocketV2.subscribe(correlation_id, mode, token_list)
                    # mode: 1 = LTP, 2 = Quote, 3 = Snap Quote
                    result = sws.subscribe(self.correlation_id, 1, token_list)
                    logging.info(f"Subscription successful: {result}")
                    
                except Exception as subscribe_error:
                    logging.error(f"Subscription failed: {subscribe_error}")
                    # Even if subscription fails, we might still get data
                    # if the connection is established
                    
            logging.info("WebSocket monitoring started")
            
            return True
            
        except Exception as e:
            logging.error(f"Error starting WebSocket: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return False

    def start_health_monitor(self):
        """Start health monitoring in separate thread"""
        def health_monitor():
            last_report = time.time()
            while self.is_running:
                try:
                    # Send health report every 5 minutes
                    if time.time() - last_report > 3000:
                        self.send_health_report()
                        last_report = time.time()
                    
                    time.sleep(10)
                    
                except Exception as e:
                    logging.error(f"Health monitor error: {e}")
                    time.sleep(30)
        
        health_thread = threading.Thread(target=health_monitor, daemon=True)
        health_thread.start()
        logging.info("Health monitor started")

    def send_health_report(self):
        """Send enhanced health report with context information"""
        active_options = sum(1 for ltp in self.last_ltp.values() if ltp > 0)
        queue_size = self.alert_queue.qsize()
        
        context_summary = self.get_context_summary()
        
        message = f"""
*ENHANCED SYSTEM HEALTH REPORT*

*Monitoring Status:* ACTIVE
*Session Duration:* {context_summary['session_duration']}
*Options Tracked:* {active_options}/{len(self.monitored_options)}
*Alert Workers:* {self.max_alert_workers}
*Queue Size:* {queue_size}
*Messages Sent:* {self.message_count}

*Performance Metrics:*
   • Avg Alert Time: {self.monitoring_context['performance_metrics']['avg_alert_processing_time']:.3f}s
   • Max Queue Size: {self.monitoring_context['performance_metrics']['max_queue_size']}
   • Data Points: {self.monitoring_context['performance_metrics']['total_data_points']}

*Position Management:*
   • Active Positions: {self.monitoring_context['position_management']['active_positions']}
   • Completed Positions: {self.monitoring_context['position_management']['completed_positions']}
   • Profitable Exits: {self.monitoring_context['position_management']['profitable_exits']}
   • Loss Exits: {self.monitoring_context['position_management']['loss_exits']}

*Trading Session:*
   • WebSocket: {'CONNECTED' if self.is_ws_connected else 'DISCONNECTED'}
   • Last Sync: {self.monitoring_context['trading_session']['last_sync_time'] or 'N/A'}

*Alerts Triggered:*
   • Entries: {len(self.alerted_entries)}
   • Targets: {len(self.alerted_targets)}
   • Stoploss: {len(self.alerted_stoploss)}

*Report Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        send_telegram_message_admin(message)
        self.update_context('last_health_report', datetime.now().isoformat())

    def save_context_snapshot(self):
        """Save current context to file for persistence"""
        try:
            snapshot = {
                'timestamp': datetime.now().isoformat(),
                'context': self.monitoring_context,
                'active_positions': list(self.entered_positions),
                'completed_positions': list(self.completed_positions),
                'alerted_entries': list(self.alerted_entries),
                'alerted_targets': list(self.alerted_targets),
                'alerted_stoploss': list(self.alerted_stoploss)
            }
            
            filename = f"context_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump(snapshot, f, indent=2)
            
            logging.info(f"Context snapshot saved: {filename}")
        except Exception as e:
            logging.error(f"Error saving context snapshot: {e}")

    def start_live_monitoring(self):
        """Start parallel live monitoring"""
        if not self.smart_api:
            logging.error("Failed to create session. Cannot start monitoring.")
            return
        
        # Start WebSocket monitoring
        ws_success = self.start_websocket_monitoring()
        
        if not ws_success:
            logging.error("WebSocket failed, cannot start parallel monitoring")
            return
        
        logging.info(f"\nSTARTING PARALLEL OPTION MONITORING")
        logging.info("=" * 80)
        logging.info(f"Monitoring {len(self.monitored_options)} options")
        logging.info(f"Alert Workers: {self.max_alert_workers}")
        logging.info(f"WebSocket Tokens: {len(self.token_map)}")
        logging.info(f"Mode: REAL-TIME PARALLEL PROCESSING")
        logging.info("=" * 80)
        
        # Start health monitor
        self.start_health_monitor()
        
        # Keep main thread alive
        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("\nParallel monitoring stopped by user")
            self.stop_monitoring()

    def stop_monitoring(self):
        """Stop all monitoring activities"""
        self.is_running = False
        
        # Stop WebSocket
        if self.web_socket:
            self.web_socket.close_connection()
        
        # Wait for alert queue to empty
        self.alert_queue.join()
        
        # Save final context snapshot
        # self.save_context_snapshot()
        
        logging.info("Parallel monitoring stopped completely")

    def find_latest_analysis_file(self):
        """Find the latest analysis JSON file"""
        analysis_dir = "stock_interaday_json"
        if not os.path.exists(analysis_dir):
            logging.error(f"Analysis directory '{analysis_dir}' not found")
            return None
        
        json_files = [f for f in os.listdir(analysis_dir) if f.endswith('.json')]
        if not json_files:
            logging.error(f"No JSON files found in '{analysis_dir}'")
            return None
        
        # Sort by modification time (newest first)
        json_files.sort(key=lambda x: os.path.getmtime(os.path.join(analysis_dir, x)), reverse=True)
        latest_file = os.path.join(analysis_dir, json_files[0])
        
        logging.info(f"Found latest analysis file: {latest_file}")
        return latest_file

def main():
    """Main function to start parallel option monitoring"""
    logging.info("PARALLEL LIVE OPTION MONITORING SYSTEM")
    logging.info("=" * 80)
    # Initialize monitor
    monitor = ParallelOptionMonitor()
    # Find latest analysis file
    latest_file = monitor.find_latest_analysis_file()
    if not latest_file:
        return
    
    # Load analysis data
    if not monitor.load_analysis_data(latest_file):
        logging.error("Failed to load analysis data")
        return
    
    # Show monitoring summary
    logging.info(f"\nPARALLEL MONITORING SUMMARY:")
    logging.info(f"   Total Options: {len(monitor.monitored_options)}")
    logging.info(f"   Alert Workers: {monitor.max_alert_workers}")
    logging.info(f"   Mode: True Parallel Processing")
    logging.info(f"   WebSocket: Real-time")
    logging.info(f"   Telegram Alerts: {'Enabled' if monitor.telegram_bot_token else 'Disabled'}")
    
    # Start parallel monitoring
    try:
        logging.info(f"\nStarting PARALLEL WebSocket monitoring...")
        logging.info("   All options monitored simultaneously")
        logging.info("   Instant alerts with parallel processing")
        logging.info("   Press Ctrl+C to stop monitoring")
        logging.info("=" * 80)
        
        monitor.start_live_monitoring()
        
    except KeyboardInterrupt:
        logging.info("\nMonitoring stopped by user")
        monitor.stop_monitoring()
    except Exception as e:
        logging.info(f"Monitoring error: {e}")
        monitor.stop_monitoring()

# if __name__ == "__main__":
#     main()