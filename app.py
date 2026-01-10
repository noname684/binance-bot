import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

MONGO_URL = os.getenv("MONGO_URL")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "1000PEPEUSDT", "SUIUSDT", "XRPUSDT", "1000WHYUSDT"]

# 1. ПОДКЛЮЧЕНИЕ К БАЗЕ И ЗАГРУЗКА ДАННЫХ
try:
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    db = client.market_monitor
    collection = db.daily_stats
except: client = None

def load_from_db():
    today = datetime.now().strftime("%Y-%m-%d")
    default = {s: {"p":0, "ls":0, "tb":0, "ts":0, "mb":0, "ms":0, "l":0, "sh":0, "ex":0, "liq":0, "oi":0, "v":0} for s in SYMBOLS}
    if client:
        try:
            doc = collection.find_one({"date": today})
            if doc and "assets" in doc:
                # Берем старые данные и дополняем их новыми ключами если нужно
                for s in SYMBOLS:
                    if s in doc["assets"]:
                        default[s].update(doc["assets"][s])
                return default
        except: pass
    return default

# Инициализируем данные из базы при старте
data_store = load_from_db()

def monitor():
    global data_store
    prev = {}
    while True:
        today = datetime.now().strftime("%Y-%m-%d")
        for s in SYMBOLS:
            try:
                t = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={s}", timeout=5).json()
                o = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                ls = requests.get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={s}&period=5m&limit=1", timeout=5).json()
                dv = requests.get(f"https://fapi.binance.com/futures/data/takerbuybuyvol?symbol={s}&period=5m&limit=1", timeout=5).json()
                
                p = float(t['lastPrice'])
                oi_usd = float(o['openInterest']) * p
                tb = float(dv[0]['buyVol']) * p if dv else 0
                ts = (float(dv[0]['vol']) * p) - tb if dv else 0
                
                data_store[s].update({
                    "p": p, "ls": float(ls[0]['longShortRatio']) if ls else 0, 
                    "tb": tb, "ts": ts, "mb": ts, "ms": tb, "oi": oi_usd, "v": float(t['quoteVolume'])
                })

                if s in prev:
                    d_oi = oi_usd - prev[s]['oi']
                    d_p = p - prev[s]['p']
                    if d_oi > 0:
                        if d_p >= 0: data_store[s]['l'] += d_oi
                        else: data_store[s]['sh'] += d_oi
                    else:
                        data_store[s]['ex'] += abs(d_oi)
                        if abs(d_p/p) > 0.0015: data_store[s]['liq'] += abs(d_oi)
                
                prev[s] = {"oi": oi_usd, "p": p}
            except: pass
        
        # СОХРАНЕНИЕ В БАЗУ КАЖДЫЙ ЦИКЛ
        if client:
            try:
                collection.update_one({"date": today}, {"$set": {"assets": data_store}}, upsert=True)
            except: pass
            
        time.sleep(10)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers()
        rows = ""
        for s in SYMBOLS:
            d = data_store[s]
            tb, ts = d.get('tb', 0), d.get('ts', 0)
            total = tb + ts
            pres = ((tb - ts) / total * 100) if total > 0 else 0
            pres_clr = "#00ff88" if pres > 0 else "#ff4444"

            rows += f"<tr><td style='color:#00ff88;'><b>{s}</b></td><td>{d['p']:,.4f}</td><td>{d['ls']:.2f}</td><td style='color:{pres_clr}'>{pres:+.1f}%</td><td>${tb:,.0f}</td><td>${ts:,.0f}</td><td style='color:#00ff88; opacity:0.5;'>${d['mb']:,.0f}</td><td style='color:#ff4444; opacity:0.5;'>${d['ms']:,.0f}</td><td style='border-left:2px solid #333; color:#00ff88;'>${d['l']:,.0f}</td><td style='color:#ff4444;'>${d['sh']:,.0f}</td><td style='color:#ffaa00;'>${d['ex']:,.0f}</td><td style='color:#ff0055;'>${d['liq']:,.0f}</td><td style='color:#00d9ff;'>${d['oi']:,.0f}</td></tr>"
        
        self.wfile.write(f"<html><head><meta http-equiv='refresh' content='10'><style>body{{background:#050505;color:#eee;font-family:sans-serif;padding:20px;}}table{{width:100%;border-collapse:collapse;}}th{{background:#111;padding:12px;color:#444;font-size:10px;text-align:left;}}td{{padding:12px;border-bottom:1px solid #181818;font-size:13px;}}</style></head><body><h1>WHALE RADAR v3.6 (WITH DB MEMORY)</h1><table><tr><th>Symbol</th><th>Price</th><th>L/S</th><th>Press</th><th>Taker Buy</th><th>Taker Sell</th><th>Maker Buy</th><th>Maker Sell</th><th style='border-left:2px solid #333;'>Longs(OI)</th><th>Shorts(OI)</th><th>Exits</th><th>Liq</th><th>OI USD</th></tr>{rows}</table></body></html>".encode())

threading.Thread(target=monitor, daemon=True).start()
HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), H).serve_forever()
