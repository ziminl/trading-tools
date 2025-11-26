##request.py

import requests
import json

url = "http://<server_ip>:8080/webhook"

payload = {
    "passphrase": "YOUR_SECRET_TRADINGVIEW_PHRASE",
    "symbol": "BNB/USDT:USDT",
    "side": "buy",
    "amount": 1.5,
    "tp_percent": 3.0,
    "sl_percent": 1.5
}

headers = {"Content-Type": "application/json"}

response = requests.post(url, data=json.dumps(payload), headers=headers)

print("Status:", response.status_code)
print("Response:", response.text)
                                        
