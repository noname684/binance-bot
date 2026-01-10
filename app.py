import requests, time, threading, os, json
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

# Пытаемся импортировать websocket, чтобы Render не ругался
try:
    import websocket
except ImportError:
    print("Module websocket-client not found")

SYMBOLS = ["btcusdt", "ethusdt"]
# Главное хранилище
data_store = {s.upper(): {"p":0.0, "ls":0.0, "tb":0, "ts":0, "l":0, "sh":0, "ex":0, "oi":0} for s in SYMBOLS}
prev_data = {}

# Подключение к базе для истории
MONGO_URL = os.getenv("MONGO_URL")
try:
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=2000)
    collection = client.market_monitor.daily_stats
    doc = collection.find_one({"date": datetime.now().strftime("%Y-%m-%d")})
    if doc and "assets" in doc:
        for s in data_store:
            if s in doc["assets"]:
                for key in ["l", "sh", "ex"]:
                    data_store[s][key] = doc["assets"][s].get(key, 0)
except: client = None

# --- ПОТОК 1: ЖИВЫЕ ЦЕНЫ (WEBSOCKET) ---
def on_message(ws, message):
    msg = json.loads(message)
    symbol = msg['s']
    if symbol in data_store:
        data_store[symbol]["p"] = float(msg['c'])

def run_ws():
    streams = "/".join([f"{s}@ticker" for s in SYMBOLS])
    ws = websocket.WebSocketApp(f"wss://fstream.binance.com/ws/{streams}", on_message=on_message)
    while True:
        ws.run_forever()
        time.sleep(5)

# --- ПОТОК 2: СТАТИСТИКА (OI, L/S) ---
def fetch_stats():
    global prev_data
    while True:
        for s in data_store:
            try:
                p = data_store[s]["p"]
                if p == 0: continue
                # Запросы к API (делаем редко, чтобы не забанили)
                r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                r_ls = requests.get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={s}&period=5m&limit=1", timeout=5).json()
                r_vol = requests.get(f"https://fapi.binance.com/futures/data/takerbuybuyvol?symbol={s}&period=5m&limit=1", timeout=5).json()
                
                oi_usd = float(r_oi['openInterest']) * p
                tb = float(r_vol[0]['buyVol']) * p if r_vol else 0
                ts = (float(r_vol[0]['vol']) * p) - tb if r_vol else 0
                
                data_store[s].update({"ls": float(r_ls[0]['longShortRatio']) if r_ls else 0, "tb": tb, "ts": ts, "oi": oi_usd})

                if s in prev_data:
                    d_oi = oi_usd - prev_data[s]['oi']
                    d_p = p - prev_data[s]['p']
                    if d_oi > 0:
                        if d_p >= 0: data_store[s]['l'] += d_oi
                        else: data_store[s]['sh'] += d_oi
                    else: data_store[s]['ex'] += abs(d_oi)
                
                prev_data[s] = {"oi": oi_usd, "p": p}
                time.sleep(5) # Пауза между запросами
            except: pass
        if client: # Сохранение в БД
            try: collection.update_one({"date": datetime.now().strftime("%Y-%m-%d")}, {"$set": {"assets": data_store}}, upsert=True)
            except: pass
        time.sleep(30)

# --- ВЕБ ИНТЕРФЕЙС ---
class UI(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers()
        rows = ""
        for s, d in data_store.items():
            p = d['p']
            tb, ts = d['tb'], d['ts']
            pres = ((tb - ts) / (tb + ts) * 100) if (tb + ts) > 0 else 0
            rows += f"""<tr>
                <td style='color:#00ff88; font-size:24px;'><b>{s}</b></td>
                <td style='font-family:monospace; font-size:28px;'>{p:,.2f}</td>
                <td style='font-size:22px; color:#aaa;'>{d['ls']:.2f}</td>
                <td style='color:{'#00ff88' if pres > 0 else '#ff4444'}; font-size:22px;'>{pres:+.1f}%</td>
                <td>${tb:,.0f}</td><td>${ts:,.0f}</td>
                <td style='border-left:3px solid #333; color:#00ff88; font-size:20px;'>${d['l']:,.0f}</td>
                <td style='color:#ff4444; font-size:20px;'>${d['sh']:,.0f}</td>
                <td style='color:#ffaa00; font-size:20px;'>${d['ex']:,.0f}</td>
                <td style='color:#00d9ff;'>${d['oi']:,.0f}</td>
            </tr>"""
        self.wfile.write(f"<html><head><meta http-equiv='refresh' content='10'><style>body{{background:#050505; color:#eee; font-family:sans-serif; padding:40px;}}table{{width:100%; border-collapse:collapse; background:#0a0a0a; border-radius:15px;}}th{{background:#111; padding:20px; color:#444; font-size:12px; text-align:left; text-transform:uppercase;}}td{{padding:25px; border-bottom:1px solid #181818;}}</style></head><body><h1>WHALE RADAR v4.0 PRO (WS)</h1><table><tr><th>Symbol</th><th>Price</th><th>L/S</th><th>Press</th><th>Taker Buy</th><th>Taker Sell</th><th style='border-left:3px solid #333;'>Longs (Day)</th><th>Shorts (Day)</th><th>Exits (Day)</th><th>OI USD</th></tr>{rows}</table></body></html>".encode())

threading.Thread(target=run_ws, daemon=True).start()
threading.Thread(target=fetch_stats, daemon=True).start()
HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), UI).serve_forever()
