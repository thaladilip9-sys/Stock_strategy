from twilio.rest import Client
from dotenv import load_dotenv
import os,requests,logging
load_dotenv('./env/.env.prod')

TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')      
TWILIO_WHATSAPP_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER')
YOUR_WHATSAPP_NUMBER = os.getenv('DILIP_WHATSAPP_NUMBER')

def send_whatsapp_message(message):
    """Send message via Twilio WhatsApp API"""
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        message = client.messages.create(
            body=message,
            from_=TWILIO_WHATSAPP_NUMBER,
            to=YOUR_WHATSAPP_NUMBER
        )
        
        print(f"✅ WhatsApp message sent! SID: {message.sid}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send WhatsApp message: {e}")
        return False
    

    
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def send_telegram_message(message: str):
    """Send message via Telegram Bot API"""
    
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("✅ Telegram message sent!")
            return True
        else:
            print(f"❌ Failed to send Telegram message: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception while sending Telegram message: {e}")
        return False
    
CHAT_ID_ADMIN = os.getenv("TELEGRAM_CHAT_ID_ADMIN")

logging.info("Admin Chat ID:", CHAT_ID_ADMIN)  # Print first 5 characters for verification

def send_telegram_message_admin(message: str):
    """Send message via Telegram Bot API to Admin"""
    
    payload = {
        "chat_id": CHAT_ID_ADMIN,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("✅ Telegram Admin message sent!")
            return True
        else:
            print(f"❌ Failed to send Telegram Admin message: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception while sending Telegram Admin message: {e}")
        return False
    