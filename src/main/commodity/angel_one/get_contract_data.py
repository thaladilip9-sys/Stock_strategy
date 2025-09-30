# get_contract_data_enhanced.py
import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('./env/.env.prod')

def get_mcx_instruments():
    """Get MCX instruments from Angel One's public API"""
    try:
        print("📥 Downloading MCX instruments from Angel One...")
        
        url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        all_instruments = response.json()
        
        mcx_instruments = [
            inst for inst in all_instruments 
            if inst.get('exch_seg') == 'MCX'
        ]
        
        print(f"✅ Loaded {len(mcx_instruments)} MCX instruments")
        return mcx_instruments
        
    except Exception as e:
        print(f"❌ Error fetching MCX instruments: {e}")
        return None

def parse_expiry_date(expiry_str):
    """Parse expiry string to datetime object"""
    try:
        return datetime.strptime(expiry_str, '%d%b%Y')
    except ValueError:
        return None

def filter_and_sort_contracts(contracts, symbol_name):
    """Filter and sort contracts by expiry date"""
    valid_contracts = []
    
    for contract in contracts:
        expiry_str = contract.get('expiry', '')
        symbol = contract.get('symbol', '')
        token = contract.get('token', '')
        
        # Additional filtering to ensure we get the right contract type
        if (expiry_str and symbol and token and 
            symbol.startswith(symbol_name) and 
            'FUT' in symbol and
            'IC' not in symbol):  # Exclude IC contracts if needed
            
            expiry_date = parse_expiry_date(expiry_str)
            if expiry_date:
                contract['expiry_date'] = expiry_date
                contract['expiry_days'] = (expiry_date - datetime.now()).days
                valid_contracts.append(contract)
    
    # Sort by expiry date (ascending - nearest first)
    valid_contracts.sort(key=lambda x: x['expiry_date'])
    
    return valid_contracts

def smart_mcx_contracts():
    """Get MCX contracts data with enhanced filtering"""
    
    instruments = get_mcx_instruments()
    if not instruments:
        return None, None
    
    goldm_data = None
    silverm_data = None
    
    print("\n🎯 CONTRACT SELECTION (Ascending order, >10 days expiry):")
    print("=" * 70)
    
    # Process GOLDM
    print(f"\n🔍 GOLDM Contracts:")
    goldm_contracts = [inst for inst in instruments if inst.get('symbol', '').startswith('GOLDM') and 'FUT' in inst.get('symbol', '')]
    goldm_valid = filter_and_sort_contracts(goldm_contracts, 'GOLDM')
    
    for contract in goldm_valid:
        symbol = contract.get('symbol', '')
        expiry_str = contract.get('expiry', '')
        expiry_days = contract['expiry_days']
        
        if expiry_days >= 10 and not goldm_data:
            goldm_data = contract
            print(f"✅ SELECTED: {symbol}")
            print(f"   Expiry: {expiry_str} ({expiry_days} days left)")
            print(f"   Token: {contract.get('token')}")
            
            # Add required fields
            contract['trading_symbol'] = symbol
            contract['instrument_key'] = f"MCX_FUT_{contract.get('token')}"
        else:
            status = "SKIPPED" if expiry_days < 10 else "available"
            print(f"   {symbol} - {expiry_str} ({expiry_days}d) - {status}")
    
    # Process SILVERM
    print(f"\n🔍 SILVERM Contracts:")
    silverm_contracts = [inst for inst in instruments if inst.get('symbol', '').startswith('SILVERM') and 'FUT' in inst.get('symbol', '') and 'IC' not in inst.get('symbol', '')]
    silverm_valid = filter_and_sort_contracts(silverm_contracts, 'SILVERM')
    
    for contract in silverm_valid:
        symbol = contract.get('symbol', '')
        expiry_str = contract.get('expiry', '')
        expiry_days = contract['expiry_days']
        
        if expiry_days >= 10 and not silverm_data:
            silverm_data = contract
            print(f"✅ SELECTED: {symbol}")
            print(f"   Expiry: {expiry_str} ({expiry_days} days left)")
            print(f"   Token: {contract.get('token')}")
            
            # Add required fields
            contract['trading_symbol'] = symbol
            contract['instrument_key'] = f"MCX_FUT_{contract.get('token')}"
        else:
            status = "SKIPPED" if expiry_days < 10 else "available"
            print(f"   {symbol} - {expiry_str} ({expiry_days}d) - {status}")
    
    return goldm_data, silverm_data

# if __name__ == "__main__":
#     goldm, silverm = smart_mcx_contracts()
    
#     if goldm:
#         print(f"\n🎯 Final GOLDM: {goldm.get('symbol')} | Expiry: {goldm.get('expiry')} | Token: {goldm.get('token')}")
#     if silverm:
#         print(f"🎯 Final SILVERM: {silverm.get('symbol')} | Expiry: {silverm.get('expiry')} | Token: {silverm.get('token')}")