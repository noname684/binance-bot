import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

# Оставляем только главных игроков
SYMBOLS = ["BTCUSDT", "ETHUSDT"]
MONGO_URL = os.getenv("MONGO_URL")

data_store = {s: {"p":0.0, "ls":0.0, "tb":0, "ts":0, "l":0, "sh":0, "ex":0, "oi":0} for s in SYMBOLS}
prev_data = {}

try:
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=2000)
    collection = client.market_monitor.daily_stats
    doc = collection.find_one({"date": datetime.now().strftime("%Y-%m-%d")})
    if doc and "assets" in doc:
        for s in SYMBOLS:
            if s in doc["assets"]:
                for key in ["l", "sh", "ex"]:
                    data_store[s][key] = doc["assets"][s].get(key, 0)
except: client = None

def fetch_data():
    global data_store, prev_data
    while True:
        try:
            # Запрашиваем цены сразу для всех (меньше нагрузки)
            all_p = requests.get("https://fapi.binance.com/fapi/v1/ticker/price", timeout=5).json()
            prices = {t['symbol']: float(t['price']) for t in all_p if t['symbol'] in SYMBOLS}
            
            for s in SYMBOLS:
                if s not in prices: continue
                p = prices[s]
                
                # Поочередные запросы с паузами
                oi_d = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=3).json()
                time.sleep(1) 
                ls_d = requests.get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={s}&period=5m&limit=1", timeout=3).json()
                time.sleep(1)
                vol_d = requests.get(f"https://fapi.binance.com/futures/data/takerbuybuyvol?symbol={s}&period=5m&limit=1", timeout=3).json()
                
                oi_usd = float(oi_d['openInterest']) * p
                tb = float(vol_d[0]['buyVol']) * p if vol_d else 0
                ts = (float(vol_d[0]['vol']) * p) - tb if vol_d else 0
                
                data_store[s].update({
                    "p": p, "ls": float(ls_d[0]['longShortRatio']) if ls_d else 0,
                    "tb": tb, "ts": ts, "oi": oi_usd
                })

                if s in prev_data:
                    d_oi = oi_usd - prev_data[s]['oi']
                    d_p = p - prev_data[s]['p']
                    if d_oi > 0:
                        if d_p >= 0: data_store[s]['l'] += d_oi
                        else: data_store[s]['sh'] += d_oi
                    else:
                        data_store[s]['ex'] += abs(d_oi)
                
                prev_data[s] = {"oi": oi_usd, "p": p}
                time.sleep(2) # Большая пауза между BTC и ETH
        except: pass
        time.sleep(10)

def save_to_db():
    if not client: return
    while True:
        try:
            collection.update_one({"date": datetime.now().strftime("%Y-%m-%d")}, {"$set": {"assets": data_store}}, upsert=True)
        except: pass
        time.sleep(60)

class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers()
        rows = ""
        for s in SYMBOLS:
            d = data_store[s]
            p = d['p']
            p_str = f"{p:,.2f}" if p > 0 else "<span style='color:#f00;'>CONNECTING...</span>"
            tb, ts = d['tb'], d['ts']
            pres = ((tb - ts) / (tb + ts) * 100) if (tb + ts) > 0 else 0
            
            rows += f"""<tr>
                <td style='color:#00ff88; font-size:22px;'><b>{s}</b></td>
                <td style='font-family:monospace; font-size:24px;'>{p_str}</td>
                <td style='font-size:20px;'>{d['ls']:.2f}</td>
                <td style='color:{'#00ff88' if pres > 0 else '#ff4444'}; font-size:20px; font-weight:bold;'>{pres:+.1f}%</td>
                <td style='color:#00ff88;'>${tb:,.0f}</td><td style='color:#ff4444;'>${ts:,.0f}</td>
                <td style='border-left:3px solid #333; color:#00ff88; font-size:18px;'>${d['l']:,.0f}</td>
                <td style='color:#ff4444; font-size:18px;'>${d['sh']:,.0f}</td>
                <td style='color:#ffaa00; font-size:18px;'>${d['ex']:,.0f}</td>
                <td style='color:#00d9ff;'>${d['oi']:,.0f}</td>
            </tr>"""
        
        self.wfile.write(f"""<html><head><meta http-equiv='refresh' content='10'><style>
            body{{background:#000;color:#eee;font-family:sans-serif;padding:30px;}}
            table{{width:100%;border-collapse:collapse;background:#0a0a0a; border-radius:10px; overflow:hidden;}}
            th{{background:#1a1a1a;padding:20px;color:#666;font-size:12px;text-align:left;text-transform:uppercase;}}
            td{{padding:20px;border-bottom:1px solid #222;}}
        </style></head><body>
            <h1 style='color:#00ff88; font-size:32px;'>ELITE WHALE RADAR v3.8</h1>
            <table><tr>
                <th>Symbol</th><th>Price</th><th>L/S</th><th>Press (5m)</th><th>Taker Buy</th><th>Taker Sell</th>
                <th style='border-left:3px solid #333;'>Longs (Day)</th><th>Shorts (Day)</th><th>Exits (Day)</th><th>OI USD</th>
            </tr>{rows}</table></body></html>""".encode())

threading.Thread(target=fetch_data, daemon=True).start()
threading.Thread(target=save_to_db, daemon=True).start()
HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), WebHandler).serve_forever()
