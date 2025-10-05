import os
import requests
from datetime import datetime, time as dt_time, date, timedelta
from typing import Set, Optional
import logging
import pytz
from .timezone_utils import get_ist_now, convert_to_ist, IST


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('get_market_working_days.log'),
        logging.StreamHandler()
    ]
)


class MarketHolidayManager:
    """Manage market holidays and trading days"""
    
    def __init__(self):
        self.api_key = os.getenv("UPSTOX_API_KEY")  # Get from environment
        self.holidays_cache = {}
        self.cache_expiry = {}
        
    def fetch_holidays(self, year: int = 2025) -> Set[date]:
        """Fetch market holidays from Upstox API"""
        try:
            # Check cache first
            if year in self.holidays_cache and self.cache_expiry.get(year, date.min) > date.today():
                return self.holidays_cache[year]
            
            API_URL = "https://api.upstox.com/v2/market/holidays"
            
            headers = {
                "accept": "application/json",
                "ApiKey": self.api_key
            }
            params = {"year": year}
            
            response = requests.get(API_URL, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Parse holiday dates - adjust based on actual API response structure
            holidays = set()
            if 'data' in data:
                for holiday_data in data['data']:
                    # Adjust this based on the actual API response structure
                    holiday_date_str = holiday_data.get('holiday_date') or holiday_data.get('date')
                    if holiday_date_str:
                        holiday_date = datetime.strptime(holiday_date_str, "%Y-%m-%d").date()
                        holidays.add(holiday_date)
            
            # Cache the results until end of year
            self.holidays_cache[year] = holidays
            self.cache_expiry[year] = date(year, 12, 31)
            
            logging.info(f"Fetched {len(holidays)} holidays for {year}")
            return holidays
            
        except Exception as e:
            logging.error(f"Error fetching holidays: {e}")
            # Fallback to known major Indian holidays for 2025
            return self.get_fallback_holidays(year)
    
    def get_fallback_holidays(self, year: int) -> Set[date]:
        """Fallback holiday list if API fails"""
        # Major Indian market holidays for 2025
        holidays = {
            date(2025, 1, 26),   # Republic Day
            date(2025, 3, 5),    # Maha Shivratri
            date(2025, 3, 29),   # Good Friday
            date(2025, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
            date(2025, 4, 17),   # Ramzan Id (Id-Ul-Fitr)
            date(2025, 5, 1),    # Maharashtra Day
            date(2025, 6, 16),   # Bakri Id
            date(2025, 8, 15),   # Independence Day
            date(2025, 8, 19),   # Muharram
            date(2025, 10, 2),   # Mahatma Gandhi Jayanti
            date(2025, 11, 5),   # Diwali Laxmi Pujan
            date(2025, 11, 6),   # Diwali Balipratipada
            date(2025, 12, 25),  # Christmas
        }
        return {h for h in holidays if h.year == year}
    
    def is_trading_day(self, check_date: date = None) -> bool:
        """Check if a given date is a trading day"""
        if check_date is None:
            # Use IST date
            check_date = get_ist_now().date()
        
        # Check if weekend (Saturday=5, Sunday=6)
        if check_date.weekday() >= 5:
            return False
        
        # Check if holiday
        holidays = self.fetch_holidays(check_date.year)
        if check_date in holidays:
            return False
        
        return True
    
    def get_next_trading_day(self, from_date: date = None) -> date:
        """Get the next trading day"""
        if from_date is None:
            from_date = date.today()
        
        next_day = from_date + timedelta(days=1)
        while not self.is_trading_day(next_day):
            next_day += timedelta(days=1)
        
        return next_day

class TradingHoursManager:
    """Manage trading hours for Indian stock market"""
    
    # Indian Stock Market Trading Hours (NSE/BSE)
    MARKET_OPEN = dt_time(9, 15)  # 9:15 AM
    MARKET_CLOSE = dt_time(15, 30)  # 3:30 PM
    
    def __init__(self, holiday_manager: MarketHolidayManager):
        self.holiday_manager = holiday_manager
    
    def is_trading_hours(self) -> bool:
        """Check if current time is within trading hours on a trading day"""
        ist_now = get_ist_now()
        current_time = ist_now.time()
        current_date = ist_now.date()
        
        # Check if it's a trading day
        if not self.holiday_manager.is_trading_day(current_date):
            return False
        
        # Check if within trading hours
        return self.MARKET_OPEN <= current_time <= self.MARKET_CLOSE
    
    def time_until_market_open(self) -> Optional[float]:
        """Calculate seconds until market opens"""
        now = datetime.now()
        current_time = now.time()
        current_date = now.date()
        
        # If today is not a trading day, find next trading day
        if not self.holiday_manager.is_trading_day(current_date):
            next_trading_day = self.holiday_manager.get_next_trading_day(current_date)
            next_open = datetime.combine(next_trading_day, self.MARKET_OPEN)
            return (next_open - now).total_seconds()
        
        # If before market open today
        if current_time < self.MARKET_OPEN:
            market_open_today = now.replace(
                hour=self.MARKET_OPEN.hour,
                minute=self.MARKET_OPEN.minute,
                second=0,
                microsecond=0
            )
            return (market_open_today - now).total_seconds()
        
        # If after market close today
        if current_time > self.MARKET_CLOSE:
            next_trading_day = self.holiday_manager.get_next_trading_day(current_date)
            next_open = datetime.combine(next_trading_day, self.MARKET_OPEN)
            return (next_open - now).total_seconds()
        
        return 0  # Market is open now
    
    def time_until_market_close(self) -> Optional[float]:
        """Calculate seconds until market closes"""
        if not self.is_trading_hours():
            return None
        
        now = datetime.now()
        market_close_today = now.replace(
            hour=self.MARKET_CLOSE.hour,
            minute=self.MARKET_CLOSE.minute,
            second=0,
            microsecond=0
        )
        return (market_close_today - now).total_seconds()

