import json
import time
import requests
from datetime import datetime
import os
from dotenv import load_dotenv
from SmartApi import SmartConnect
import pyotp,threading
import logging
from typing import Dict, List, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('option_level_check.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

load_dotenv('./env/.env.prod')

class AngelOneConnect:
    _instance = None
    _is_initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AngelOneConnect, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Prevent re-initialization
        if not self._is_initialized:
            self.api_key = os.getenv('ANGEL_API_KEY')
            self.client_code = os.getenv('ANGEL_CLIENT_ID')
            self.password = os.getenv('ANGEL_PASSWORD')
            self.totp_secret = os.getenv('ANGEL_TOTP')
            self.smart_api = None
            self.session_data = None
            self._is_initialized = True
            self._last_connection_time = None
            self._connection_lock = threading.Lock()
            logging.info("AngelOneConnect singleton initialized")

    def generate_totp(self):
        """Generate a TOTP code using the secret key."""
        try:
            # Clean the TOTP secret (remove spaces and make uppercase)
            totp_secret_clean = ''.join(c for c in self.totp_secret if c.isalnum()).upper()
            totp = pyotp.TOTP(totp_secret_clean)
            return totp.now()
        except Exception as e:
            logging.error(f"Error generating TOTP: {e}")
            return None

    def connect(self):
        """Establish a connection to Angel One's Smart API."""
        with self._connection_lock:  # Thread-safe connection
            try:
                # Check if we already have a valid connection
                if self._is_connection_valid():
                    logging.info("✅ Using existing Angel One connection")
                    return self.smart_api
                
                logging.info("Connecting to Angel One Smart API...")
                
                if not all([self.api_key, self.client_code, self.password, self.totp_secret]):
                    logging.error("Missing required environment variables")
                    return None
                
                self.smart_api = SmartConnect(api_key=self.api_key)
                
                totp_code = self.generate_totp()
                if not totp_code:
                    logging.error("Failed to generate TOTP")
                    return None
                
                self.session_data = self.smart_api.generateSession(
                    self.client_code,
                    self.password,
                    totp_code
                )
                
                if self.session_data and self.session_data.get('status'):
                    logging.info("✅ Successfully connected to Angel One Smart API")
                    self._last_connection_time = datetime.now()
                    
                    # Generate feed token
                    feed_token_response = self.smart_api.getfeedToken()
                    if feed_token_response:
                        logging.info("✅ Feed token generated successfully")
                    else:
                        logging.warning("⚠️ Could not generate feed token")
                    
                    return self.smart_api
                else:
                    error_msg = self.session_data.get('message', 'Unknown error') if self.session_data else 'No response'
                    logging.error(f"❌ Session generation failed: {error_msg}")
                    return None
                    
            except Exception as e:
                logging.error(f"❌ Connection failed: {e}")
                return None

    def _is_connection_valid(self):
        """Check if the current connection is still valid."""
        if not self.smart_api or not self.session_data:
            return False
        
        # Check if connection is older than 1 hour (typical session expiry)
        if self._last_connection_time:
            time_diff = (datetime.now() - self._last_connection_time).total_seconds()
            if time_diff > 3600:  # 1 hour in seconds
                logging.info("🔄 Connection expired, reconnecting...")
                return False
        
        # Optional: Add additional checks like making a test API call
        try:
            # Simple API call to verify connection
            profile = self.smart_api.getProfile()
            return profile and profile.get('status')
        except:
            return False

    def reconnect_if_needed(self):
        """Reconnect if the current connection is invalid."""
        if not self._is_connection_valid():
            logging.info("🔄 Reconnecting to Angel One...")
            return self.connect()
        return self.smart_api

    def get_session_data(self):
        """Get session data safely."""
        if self._is_connection_valid():
            return self.session_data
        return None

    def get_smart_api(self):
        """Get smart API instance safely."""
        if self._is_connection_valid():
            return self.smart_api
        return None

    @classmethod
    def get_instance(cls):
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset the singleton instance (for testing purposes)."""
        cls._instance = None
        cls._is_initialized = False