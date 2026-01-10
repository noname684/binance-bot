import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
MONGO_URL = os.getenv("MONGO_URL")

# --- ПОДКЛЮЧЕНИЕ С ПРОВЕРКОЙ ---
try:
    print(f"--- [STARTING] Connecting to: {MONGO_URL[:20]}... ---")
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    db = client.market_monitor
    collection = db.daily_stats
    # Проверка связи
    client.admin.command('ping')
    print("--- [DATABASE] SUCCESS: Connected to MongoDB! ---")
except Exception as e:
    print(f"--- [DATABASE ERROR] Check your MONGO_URL or IP Access: {e} ---")

def load_from_db():
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        data = collection.find_one({"date": today})
        if data: 
            print(f"--- [DB] Loaded data for {today} ---")
            return data
    except Exception as e:
        print(f"--- [DB LOAD ERROR] {e} ---")
    return {"date": today, "assets": {s: {"longs": 0.0, "shorts": 0.0, "exit": 0.0, "price": 0.0, "oi": 0.0, "oi_coins": 0.0, "action": "WAITING", "last_delta": 0.0, "coin_delta": 0.0} for s in SYMBOLS}}

def save_to_db(data):
    try:
        collection.replace_one({"date": data["date"]}, data, upsert=True)
        # Удалил принты отсюда, чтобы не спамить логи
    except Exception as e:
        print(f"--- [SAVE ERROR] {e} ---")

session_data = load_from_db()

# ... (код класса SmartTerminal остается таким же, как в прошлый раз) ...

def monitor():
    global session_data
    prev_oi_coins, prev_price = {}, {}
    print("--- [MONITOR] Bot started monitoring market... ---")
    while True:
        for s in SYMBOLS:
            try:
                r_p = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={s}", timeout=5).json()
                r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                
                p = float(r_p['price'])
                oi_coins = float(r_oi['openInterest'])
                oi_usd = oi_coins * p
                
                if s in prev_oi_coins:
                    d_coins = oi_coins - prev_oi_coins[s]
                    d_p = p - prev_price[s]
                    
                    action = "WAITING"
                    if d_p > 0: action = "🔥 AGRESSIVE BUY" if d_coins > 0 else "⚡ SHORT SQUEEZE"
                    elif d_p < 0: action = "💀 AGRESSIVE SELL" if d_coins > 0 else "💧 LONG FLUSH"
                    
                    asset_ref = session_data["assets"][s]
                    asset_ref.update({"price": p, "oi": oi_usd, "oi_coins": oi_coins, "action": action, "coin_delta": d_coins})
                    
                    if d_coins > 0:
                        if d_p > 0: asset_ref['longs'] += (d_coins * p)
                        else: asset_ref['shorts'] += (d_coins * p)
                    else: asset_ref['exit'] += abs(d_coins * p)
                    
                    save_to_db(session_data)
                
                prev_oi_coins[s], prev_price[s] = oi_coins, p
            except Exception as e:
                print(f"--- [API ERROR] {s}: {e} ---")
        time.sleep(15)

# (Остальная часть запуска сервера без изменений)
