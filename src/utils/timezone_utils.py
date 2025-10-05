"""Timezone utilities for handling IST timestamps"""
from datetime import datetime
import pytz

IST = pytz.timezone('Asia/Kolkata')
UTC = pytz.UTC

def get_ist_now() -> datetime:
    """Get current time in IST"""
    return datetime.now(UTC).astimezone(IST)

def convert_to_ist(dt: datetime) -> datetime:
    """Convert any datetime to IST"""
    if dt.tzinfo is None:
        dt = UTC.localize(dt)
    return dt.astimezone(IST)

def is_ist_time_between(target_time: datetime, start_time: datetime, end_time: datetime) -> bool:
    """Check if target time is between start and end times in IST"""
    if target_time.tzinfo is None:
        target_time = IST.localize(target_time)
    if start_time.tzinfo is None:
        start_time = IST.localize(start_time)
    if end_time.tzinfo is None:
        end_time = IST.localize(end_time)
    
    target_time = target_time.astimezone(IST)
    start_time = start_time.astimezone(IST)
    end_time = end_time.astimezone(IST)
    
    return start_time <= target_time <= end_time