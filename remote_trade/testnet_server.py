import ccxt
import time
import json
import sys
from flask import Flask, request, jsonify

WEBHOOK_PASSPHRASE = 'YOUR_SECRET_TRADINGVIEW_PHRASE'
FLASK_PORT = 8080

BYBIT_API_KEY = 'YOUR_BYBIT_API_KEY'
BYBIT_API_SECRET = 'YOUR_BYBIT_API_SECRET'

LEVERAGE = 10
CATEGORY = 'linear'

app = Flask(__name__)

try:
    exchange = ccxt.bybit({
        'apiKey': BYBIT_API_KEY,
        'secret': BYBIT_API_SECRET,
        'options': {
            'defaultType': 'future',
            'adjustForTimeDifference': True,
        },
    })
    exchange.set_sandbox_mode(True)
    print("Bybit testnet initialized.")
except Exception as e:
    print(f"CCXT init error: {e}")
    sys.exit()

def initialize_bybit_settings(symbol):
    try:
        exchange.load_markets()
        try:
            exchange.set_position_mode(
                hedged=False,
                symbol=symbol,
                params={'category': CATEGORY}
            )
            print(f"{symbol}: One-Way mode set.")
        except ccxt.ExchangeError as e:
            if "110025" in str(e) or "Position mode is not modified" in str(e):
                print(f"{symbol}: One-Way already set.")
            else:
                raise e
        try:
            exchange.set_leverage(
                LEVERAGE,
                symbol,
                params={'category': CATEGORY}
            )
            print(f"{symbol}: leverage {LEVERAGE}x set.")
        except ccxt.ExchangeError as e:
            if ("110041" in str(e)
                or "Leverage not modified" in str(e)
                or f"leverage must be less than or equal to {LEVERAGE}" in str(e)):
                print(f"{symbol}: leverage already {LEVERAGE}x.")
            else:
                raise e
        return True
    except ccxt.ExchangeError as e:
        print(f"Exchange error {symbol}: {e}")
        return False
    except Exception as e:
        print(f"Unknown error {symbol}: {e}")
        return False

def execute_trade(data):
    symbol = data.get('symbol')
    order_side = data.get('side').lower()
    order_amount = data.get('amount')
    tp_percent = data.get('tp_percent')
    sl_percent = data.get('sl_percent')

    if not all([symbol, order_side in ['buy', 'sell'], order_amount, tp_percent, sl_percent]):
        print(f"Parameter error: {data}")
        return False, "Invalid payload parameters"

    print(f"Order start: {symbol} {order_side} {order_amount}")
    print(f"TP: {tp_percent}% / SL: {sl_percent}%")

    if not initialize_bybit_settings(symbol):
        return False, f"Failed to initialize settings for {symbol}"

    try:
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        print(f"Current price: {current_price}")

        if order_side == 'buy':
            tp_price = current_price * (1 + tp_percent / 100)
            sl_price = current_price * (1 - sl_percent / 100)
        else:
            tp_price = current_price * (1 - tp_percent / 100)
            sl_price = current_price * (1 + sl_percent / 100)

        tp_price_fmt = exchange.price_to_precision(symbol, tp_price)
        sl_price_fmt = exchange.price_to_precision(symbol, sl_price)

        print(f"TP: {tp_price_fmt}")
        print(f"SL: {sl_price_fmt}")

        order_params = {
            'category': CATEGORY,
            'takeProfit': tp_price_fmt,
            'stopLoss': sl_price_fmt,
        }

        if order_side == 'buy':
            order = exchange.create_market_buy_order(symbol, order_amount, order_params)
        else:
            order = exchange.create_market_sell_order(symbol, order_amount, order_params)

        order_id = order['id']
        print(f"Order sent. ID: {order_id}")

        time.sleep(1)
        entry_price = None

        for _ in range(5):
            try:
                trades = exchange.fetch_my_trades(symbol, limit=5, params={'category': CATEGORY})
                t = next((x for x in trades if x['order'] == order_id), None)
                if t:
                    entry_price = t['price']
                    print(f"Entry price: {entry_price}")
                    break
                time.sleep(1)
            except:
                time.sleep(1)

        if not entry_price:
            print("Entry price not found.")
            return True, "Order placed but entry price not confirmed"

        print("Order executed successfully.")
        return True, "Order successfully executed."

    except ccxt.AuthenticationError as e:
        print(f"Auth error: {e}")
        return False, f"Authentication Error: {e}"
    except ccxt.NetworkError as e:
        print(f"Network error: {e}")
        return False, f"Network Error: {e}"
    except ccxt.ExchangeError as e:
        print(f"Exchange error: {e}")
        return False, f"Exchange Error: {e}"
    except Exception as e:
        print(f"Unknown error: {e}")
        return False, f"Unknown Error: {e}"

@app.route('/webhook', methods=['POST'])
def webhook_listener():
    try:
        data = request.get_json(force=True)
        print(json.dumps(data, indent=2))

        if data.get('passphrase') != WEBHOOK_PASSPHRASE:
            print("Invalid passphrase")
            return jsonify({'status': 'error', 'message': 'Invalid passphrase'}), 401

        success, message = execute_trade(data)

        if success:
            return jsonify({'status': 'success', 'message': message}), 200
        else:
            return jsonify({'status': 'error', 'message': message}), 500

    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({'status': 'error', 'message': f'Server error: {e}'}), 500

if __name__ == '__main__':
    print("Webhook listener started")
    app.run(host='0.0.0.0', port=FLASK_PORT, debug=False)
