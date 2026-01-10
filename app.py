import requests, time, threading, os, sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

# ПРИНУДИТЕЛЬНЫЙ ВЫВОД В ЛОГИ
print(">>> BOT STARTING UP...", flush=True)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
MONGO_URL = os.getenv("MONGO_URL")

# Проверка наличия переменной
if not MONGO_URL:
    print(">>> ERROR: MONGO_URL is missing in Render Environment Variables!", flush=True)

# 1. ПОДКЛЮЧЕНИЕ К БАЗЕ
try:
    print(f">>> CONNECTING TO MONGO...", flush=True)
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    db = client.market_monitor
    collection = db.daily_stats
    client.admin.command('ping')
    print(">>> DATABASE CONNECTED SUCCESSFULLY!", flush=True)
except Exception as e:
    print(f">>> DATABASE CONNECTION FAILED: {e}", flush=True)

# 2. ФУНКЦИИ ДАННЫХ
def save_to_db(data):
    try:
        collection.replace_one({"date": data["date"]}, data, upsert=True)
    except Exception as e:
        print(f">>> SAVE ERROR: {e}", flush=True)

# Инициализация пустых данных
session_data = {"date": datetime.now().strftime("%Y-%m-%d"), "assets": {s: {"longs": 0.0, "shorts": 0.0, "exit": 0.0, "price": 0.0, "oi": 0.0, "oi_coins": 0.0, "action": "WAITING", "coin_delta": 0.0} for s in SYMBOLS}}

# 3. МОНИТОРИНГ
def monitor():
    global session_data
    prev_oi_coins, prev_price = {}, {}
    print(">>> MONITOR THREAD STARTED", flush=True)
    while True:
        try:
            for s in SYMBOLS:
                r_p = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={s}", timeout=5).json()
                r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                
                p = float(r_p['price'])
                oi_c = float(r_oi['openInterest'])
                
                if s in prev_oi_coins:
                    d_c = oi_c - prev_oi_coins[s]
                    d_p = p - prev_price[s]
                    
                    act = "WAITING"
                    if d_p > 0: act = "🔥 BUY" if d_c > 0 else "⚡ SQUEEZE"
                    elif d_p < 0: act = "💀 SELL" if d_c > 0 else "💧 FLUSH"
                    
                    session_data["assets"][s].update({"price": p, "oi_coins": oi_c, "action": act, "coin_delta": d_c})
                    
                    if d_c > 0:
                        if d_p > 0: session_data["assets"][s]['longs'] += (d_c * p)
                        else: session_data["assets"][s]['shorts'] += (d_c * p)
                    
                    save_to_db(session_data)
                
                prev_oi_coins[s], prev_price[s] = oi_c, p
            time.sleep(15)
        except Exception as e:
            print(f">>> MONITOR LOOP ERROR: {e}", flush=True)
            time.sleep(5)

# 4. СЕРВЕР (ИНТЕРФЕЙС)
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        html = f"<html><body style='background:#000;color:#00ff88;font-family:monospace;'><h1>MONITOR ACTIVE</h1><pre>{session_data}</pre><script>setTimeout(()=>location.reload(), 10000)</script></body></html>"
        self.wfile.write(html.encode())

# 5. ЗАПУСК
if __name__ == "__main__":
    # Запуск мониторинга в отдельном потоке
    t = threading.Thread(target=monitor)
    t.daemon = True
    t.start()
    
    # Запуск веб-сервера
    port = int(os.environ.get("PORT", 10000))
    print(f">>> SERVER STARTING ON PORT {port}", flush=True)
    server = HTTPServer(('0.0.0.0', port), Handler)
    server.serve_forever()
