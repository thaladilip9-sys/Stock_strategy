import json
import time
import requests
from datetime import datetime
import os
from dotenv import load_dotenv
from SmartApi import SmartConnect
import pyotp
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
    def __init__(self):
        self.api_key = os.getenv('ANGEL_API_KEY')
        self.client_code = os.getenv('ANGEL_CLIENT_ID')
        self.password = os.getenv('ANGEL_PASSWORD')
        self.totp_secret = os.getenv('ANGEL_TOTP')
        self.smart_api = None
        self.session_data = None

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
        try:
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
                
                # Generate feed token
                feed_token_response = self.smart_api.getfeedToken()
                if feed_token_response :
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