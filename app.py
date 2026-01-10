import requests, time, threading, os, json
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime
import websocket 

SYMBOLS = ["btcusdt", "ethusdt"]
# Всё то, что ты хотел видеть в v3.6
data_store = {s.upper(): {"p":0.0, "ls":0.0, "tb":0, "ts":0, "l":0, "sh":0, "ex":0, "liq":0, "oi":0} for s in SYMBOLS}
prev_data = {}

# Подключение к базе
MONGO_URL = os.getenv("MONGO_URL")
try:
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=2000)
    collection = client.market_monitor.daily_stats
    doc = collection.find_one({"date": datetime.now().strftime("%Y-%m-%d")})
    if doc and "assets" in doc:
        for s in data_store:
            if s in doc["assets"]:
                for key in ["l", "sh", "ex", "liq"]:
                    data_store[s][key] = doc["assets"][s].get(key, 0)
except: client = None

# WEBSOCKET ДЛЯ ЦЕНЫ И ОБЪЕМА
def on_message(ws, message):
    msg = json.loads(message)
    d = msg.get('data', {})
    s = d.get('s')
    if s in data_store:
        if d.get('e') == 'aggTrade':
            val = float(d.get('q')) * float(d.get('p'))
            if d.get('m'): data_store[s]["ts"] += val
            else: data_store[s]["tb"] += val
            data_store[s]["p"] = float(d.get('p'))

def run_ws():
    streams = "/".join([f"{s}@aggTrade" for s in SYMBOLS])
    ws = websocket.WebSocketApp(f"wss://fstream.binance.com/stream?streams={streams}", on_message=on_message)
    while True:
        ws.run_forever()
        time.sleep(5)

# REST ДЛЯ OI И L/S (РАЗ В 30 СЕКУНД)
def fetch_stats():
    global prev_data
    while True:
        for s in data_store:
            try:
                p = data_store[s]["p"]
                if p == 0: continue
                r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                r_ls = requests.get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={s}&period=5m&limit=1", timeout=5).json()
                
                oi_usd = float(r_oi['openInterest']) * p
                data_store[s]["ls"] = float(r_ls[0]['longShortRatio']) if r_ls else 0
                data_store[s]["oi"] = oi_usd

                if s in prev_data:
                    d_oi = oi_usd - prev_data[s]['oi']
                    if d_oi > 0:
                        if p > prev_data[s]['p']: data_store[s]['l'] += d_oi
                        else: data_store[s]['sh'] += d_oi
                    else: data_store[s]['ex'] += abs(d_oi)
                prev_data[s] = {"oi": oi_usd, "p": p}
                time.sleep(10)
            except: pass
        if client:
            try: collection.update_one({"date": datetime.now().strftime("%Y-%m-%d")}, {"$set": {"assets": data_store}}, upsert=True)
            except: pass
        time.sleep(30)

class UI(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers()
        rows = ""
        for s, d in data_store.items():
            total = d['tb'] + d['ts']
            pres = ((d['tb'] - d['ts']) / total * 100) if total > 0 else 0
            rows += f"<tr><td><b>{s}</b></td><td>{d['p']:,.2f}</td><td>{d['ls']:.2f}</td><td style='color:{'#00ff88' if pres > 0 else '#ff4444'}'>{pres:+.1f}%</td><td>${d['tb']:,.0f}</td><td>${d['ts']:,.0f}</td><td style='border-left:2px solid #333;'>${d['l']:,.0f}</td><td>${d['sh']:,.0f}</td><td>${d['ex']:,.0f}</td><td>${d['oi']:,.0f}</td></tr>"
        self.wfile.write(f"<html><head><meta http-equiv='refresh' content='10'></head><body style='background:#050505;color:#eee;font-family:sans-serif;padding:30px;'><h1>RADAR v4.5 FINAL</h1><table border='1' cellpadding='10' style='border-collapse:collapse;width:100%;'><tr><th>Symbol</th><th>Price</th><th>L/S</th><th>Press</th><th>Taker Buy</th><th>Taker Sell</th><th>Longs</th><th>Shorts</th><th>Exits</th><th>OI USD</th></tr>{rows}</table></body></html>".encode())

threading.Thread(target=run_ws, daemon=True).start()
threading.Thread(target=fetch_stats, daemon=True).start()
HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), UI).serve_forever()
