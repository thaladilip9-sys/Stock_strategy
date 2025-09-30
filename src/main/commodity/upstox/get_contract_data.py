import requests
import gzip
import json
import io
from datetime import datetime

def smart_mcx_contracts():
    """Simple version - paste and run"""
    
    # Download MCX data
    url = "https://assets.upstox.com/market-quote/instruments/exchange/MCX.json.gz"
    
    try:
        print("📥 Downloading MCX data...")
        response = requests.get(url, timeout=10)
        instruments = json.load(gzip.GzipFile(fileobj=io.BytesIO(response.content)))
        print(f"✅ Loaded {len(instruments)} instruments")        
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    # Commodities to analyze
    commodities = [
        ('GOLDM FUT', 'GOLDM'),
        ('SILVERM FUT', 'SILVERM')
    ]
    
    print("\n🎯 CONTRACT SELECTION (Skipping contracts expiring within 10 days):")
    print("=" * 70)
    
    for symbol, name in commodities:
        # Find futures contracts
        contracts = [
            inst for inst in instruments
            if inst.get('trading_symbol', '').startswith(symbol)
        ]
        
        if not contracts:
            print(f"❌ No contracts found for {name}")
            continue
        
        # Sort by expiry
        contracts.sort(key=lambda x: x.get('expiry', 0))
        
        print(f"\n🔍 {name}:")
        selected = None
        
        for contract in contracts:
            expiry_ms = contract.get('expiry')
            if expiry_ms:
                expiry_days = (datetime.fromtimestamp(expiry_ms/1000) - datetime.now()).days
                expiry_date = datetime.fromtimestamp(expiry_ms/1000).strftime('%d %b %Y')
                
                if expiry_days > 10 and not selected:
                    selected = contract
                    print(f"✅ SELECTED: {contract['trading_symbol']}")
                    
                    print(f"   Expiry: {expiry_date} ({expiry_days} days left)")

                    if 'GOLDM FUT' in contract['trading_symbol']:
                        goldm_data=contract
                    elif 'SILVERM FUT' in contract['trading_symbol']:
                        silverm_data=contract
                else:
                    print(f"   {contract['trading_symbol']} - {expiry_date} ({expiry_days}d)")
                    
    return goldm_data, silverm_data