import os
import time
import logging
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

client = Client(API_KEY, API_SECRET)

# Logging setup
log_file = 'btcbot3_run.log'
logger = logging.getLogger()
logger.setLevel(logging.INFO)

fh = logging.FileHandler(log_file)
fh.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))

ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))

logger.addHandler(fh)
logger.addHandler(ch)

# Telegram notifier
def send_telegram_message(message):
    try:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            logging.warning("Telegram credentials missing. Skipping notification.")
            return
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.post(url, data=payload)
    except Exception as e:
        logging.error(f"❌ Telegram Error: {e}")

# Utility: Get BTC precision
def get_btc_precision():
    symbol_info = client.get_symbol_info('BTCUSDT')
    lot_size_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE')
    step_size = float(lot_size_filter['stepSize'])
    return len('{:f}'.format(step_size).split('.')[1].rstrip('0'))

BTC_PRECISION = get_btc_precision()
TRADE_AMOUNT_USDT = 20
last_trade_price = None
last_action = None  # 'buy' or 'sell'

def get_price():
    return float(client.get_symbol_ticker(symbol="BTCUSDT")['price'])

def get_balances():
    usdt = float(client.get_asset_balance(asset='USDT')['free'])
    btc = float(client.get_asset_balance(asset='BTC')['free'])
    return usdt, btc

def execute_buy():
    try:
        usdt, _ = get_balances()
        if usdt < TRADE_AMOUNT_USDT:
            logging.warning("⚠️ Insufficient USDT to buy.")
            return False

        price = get_price()
        btc_amount = round(TRADE_AMOUNT_USDT / price, BTC_PRECISION)

        order = client.order_market_buy(symbol='BTCUSDT', quantity=btc_amount)
        msg = f"✅ Bought ${TRADE_AMOUNT_USDT} BTC at ${price:.2f} (~{btc_amount} BTC)"
        logging.info(msg)
        send_telegram_message(msg)
        return price

    except Exception as e:
        logging.error(f"❌ Buy error: {e}")
        send_telegram_message(f"❌ Buy error: {e}")
        return False

def execute_sell():
    try:
        _, btc = get_balances()
        if btc <= 0:
            logging.warning("⚠️ No BTC to sell.")
            return False

        btc_amount = round(btc, BTC_PRECISION)
        order = client.order_market_sell(symbol='BTCUSDT', quantity=btc_amount)
        price = get_price()

        msg = f"✅ Sold {btc_amount} BTC at ${price:.2f}"
        logging.info(msg)
        send_telegram_message(msg)
        return price

    except Exception as e:
        logging.error(f"❌ Sell error: {e}")
        send_telegram_message(f"❌ Sell error: {e}")
        return False

if __name__ == "__main__":
    logging.info("🤖 BTCBot3 started — trading on 1% dips and 5% pumps.")

    while True:
        try:
            price = get_price()
            usdt, btc = get_balances()

            if last_action == "sell" or last_action is None:
                # Ready to buy if price drops 1% from last trade price
                if last_trade_price is None or price <= last_trade_price * 0.99:
                    new_price = execute_buy()
                    if new_price:
                        last_trade_price = new_price
                        last_action = "buy"

            elif last_action == "buy":
                # Ready to sell if price rises 5% from last buy
                if price >= last_trade_price * 1.05:
                    new_price = execute_sell()
                    if new_price:
                        last_trade_price = new_price
                        last_action = "sell"

            logging.info(f"📊 Current Price: ${price:.2f}, Last Trade: ${last_trade_price}, Action: {last_action}")
            time.sleep(60)

        except Exception as e:
            logging.error(f"❌ Main loop error: {e}")
            send_telegram_message(f"❌ Main loop error: {e}")
            time.sleep(60)
