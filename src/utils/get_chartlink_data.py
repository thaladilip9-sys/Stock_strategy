import requests
import re

def fetch_chartink_data(input_payload):
    """Fetch data from Chartink using CSRF token"""
    # Step 1: Start a session
    session = requests.Session()
    url = "https://chartink.com/screener"

    # Get the screener page
    resp = session.get(url)
    html = resp.text

    # Extract CSRF token from the HTML meta tag
    csrf_token = re.search(r'meta name="csrf-token" content="(.*?)"', html).group(1)

    # print("CSRF Token:", csrf_token)

    # Step 2: Use token in headers for POST
    post_url = "https://chartink.com/screener/process"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRF-TOKEN": csrf_token,
        "Referer": url,
        "Origin": "https://chartink.com",
    }

    payload = {
        "scan_clause": input_payload,
    }

    resp2 = session.post(post_url, data=payload, headers=headers)

    # print(resp2.json()['data'])
    data=resp2.json()['data']
    return data