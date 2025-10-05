import requests
import json

def get_stock_details(stock_data):
    """Search for your specific stocks"""
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    
    response = requests.get(url)
    instruments = response.json()
    
    # Your stocks data
    # your_stocks = [
    #     {'nsecode': 'HAL', 'name': 'Hindustan Aeronautics Ltd', 'bsecode': '541154'},
    #     # {'nsecode': 'PIIND', 'name': 'Pi Industries Limited', 'bsecode': '523642'},
    #     # {'nsecode': 'SIEMENS', 'name': 'Siemens Limited', 'bsecode': '500550'},
    #     # {'nsecode': 'CIPLA', 'name': 'Cipla Limited', 'bsecode': '500087'}
    # ]
    
    # print("🔍 SEARCHING FOR YOUR STOCKS BY NAME:")
    # print("=" * 70)
    
    found_stocks = []
    found_options=[]
    
    for stock in stock_data:
        company_name = stock['name']
        nse_code = stock['nsecode']
        
        # print(f"\n🎯 Searching: {company_name} ({nse_code})")
        # print("-" * 50)
        
        for instrument in instruments:
            name = instrument.get('name', '').upper()
            symbol = instrument.get('symbol', '').upper()

            
            # Search by company name
            if nse_code.upper()== name and instrument["exch_seg"]=="NSE":
                # print(instrument)
                # print("Token:", instrument.get('token'))
                found_stocks.append(instrument)
            elif instrument["exch_seg"]=="NFO" and nse_code.upper()==name:
                
                found_options.append(instrument)

    stock_data={
        'stocks':found_stocks,
        'options':found_options
    }

    
    return stock_data

# if __name__ == "__main__":
#     # Search for your specific stocks
#     stock_data = get_stock_details(stock_data)
    
#     # Find alternative aerospace stocks
#     # find_any_aerospace_stocks()
    
#     if stock_data:
#         print(f"\n🎯 USE THESE TOKENS:")
#         for stock in stock_data['stocks']:
#             print(f"{stock['name']} ({stock['symbol']}): Token {stock['token']}")