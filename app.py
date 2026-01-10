import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "1000PEPEUSDT", "SUIUSDT", "XRPUSDT", "1000WHYUSDT"]
MONGO_URL = os.getenv("MONGO_URL")

# Инициализация хранилища данных
data_store = {s: {"p":0.0, "ls":0.0, "tb":0, "ts":0, "mb":0, "ms":0, "l":0, "sh":0, "ex":0, "liq":0, "oi":0, "v":0} for s in SYMBOLS}
prev_data = {}

# Подключение к БД
try:
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=2000)
    collection = client.market_monitor.daily_stats
    # Первичная загрузка накопленных данных
    doc = collection.find_one({"date": datetime.now().strftime("%Y-%m-%d")})
    if doc and "assets" in doc:
        for s in SYMBOLS:
            if s in doc["assets"]:
                for key in ["l", "sh", "ex", "liq"]:
                    data_store[s][key] = doc["assets"][s].get(key, 0)
except:
    client = None

def fetch_market_data():
    global data_store, prev_data
    while True:
        for s in SYMBOLS:
            try:
                # 1. Сначала самое важное - ЦЕНА
                r_p = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={s}", timeout=2).json()
                price = float(r_p['price'])
                
                # 2. Остальные данные
                r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=2).json()
                r_ls = requests.get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={s}&period=5m&limit=1", timeout=2).json()
                r_vol = requests.get(f"https://fapi.binance.com/futures/data/takerbuybuyvol?symbol={s}&period=5m&limit=1", timeout=2).json()
                
                oi_usd = float(r_oi['openInterest']) * price
                tb = float(r_vol[0]['buyVol']) * price if r_vol else 0
                ts = (float(r_vol[0]['vol']) * price) - tb if r_vol else 0
                
                # Обновляем LIVE-данные
                data_store[s].update({
                    "p": price, 
                    "ls": float(r_ls[0]['longShortRatio']) if r_ls else 0,
                    "tb": tb, "ts": ts, "mb": ts, "ms": tb, "oi": oi_usd
                })

                # Расчет накопленной динамики (OI)
                if s in prev_data:
                    d_oi = oi_usd - prev_data[s]['oi']
                    d_p = price - prev_data[s]['p']
                    if d_oi > 0:
                        if d_p >= 0: data_store[s]['l'] += d_oi
                        else: data_store[s]['sh'] += d_oi
                    else:
                        data_store[s]['ex'] += abs(d_oi)
                
                prev_data[s] = {"oi": oi_usd, "p": price}
            except: continue
        time.sleep(5) # Быстрое обновление каждые 5 секунд

def save_to_db():
    if not client: return
    while True:
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            collection.update_one({"date": today}, {"$set": {"assets": data_store}}, upsert=True)
        except: pass
        time.sleep(30) # Сохраняем в базу раз в 30 сек, чтобы не тормозить процесс

class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers()
        rows = ""
        for s in SYMBOLS:
            d = data_store[s]
            p = d['p']
            p_str = f"{p:,.4f}" if p > 0 else "<span style='color:red;'>OFFLINE</span>"
            
            tb, ts = d['tb'], d['ts']
            pres = ((tb - ts) / (tb + ts) * 100) if (tb + ts) > 0 else 0
            
            rows += f"""<tr>
                <td style='color:#00ff88; font-size:16px;'><b>{s}</b></td>
                <td style='font-family:monospace; font-size:18px; color:#fff;'>{p_str}</td>
                <td style='color:#aaa;'>{d['ls']:.2f}</td>
                <td style='color:{'#00ff88' if pres > 0 else '#ff4444'}; font-weight:bold;'>{pres:+.1f}%</td>
                <td style='color:#00ff88;'>${tb:,.0f}</td><td style='color:#ff4444;'>${ts:,.0f}</td>
                <td style='color:#00ff88; opacity:0.4;'>${ts:,.0f}</td><td style='color:#ff4444; opacity:0.4;'>${tb:,.0f}</td>
                <td style='border-left:2px solid #333; color:#00ff88;'>${d['l']:,.0f}</td>
                <td style='color:#ff4444;'>${d['sh']:,.0f}</td>
                <td style='color:#ffaa00;'>${d['ex']:,.0f}</td>
                <td style='color:#00d9ff;'>${d['oi']:,.0f}</td>
            </tr>"""
        
        self.wfile.write(f"""<html><head><meta http-equiv='refresh' content='10'><style>
            body{{background:#050505;color:#eee;font-family:sans-serif;padding:20px;}}
            table{{width:100%;border-collapse:collapse;background:#0a0a0a;}}
            th{{background:#111;padding:12px;color:#444;font-size:10px;text-align:left;text-transform:uppercase;}}
            td{{padding:12px;border-bottom:1px solid #181818;font-size:14px;}}
        </style></head><body>
            <h1 style='color:#00ff88;'>WHALE RADAR v3.6.2 PRO</h1>
            <table><tr>
                <th>Symbol</th><th>Live Price</th><th>L/S</th><th>Press</th><th>Taker Buy</th><th>Taker Sell</th><th>Maker Buy</th><th>Maker Sell</th>
                <th style='border-left:2px solid #333;'>Longs(OI)</th><th>Shorts(OI)</th><th>Exits</th><th>OI USD</th>
            </tr>{rows}</table></body></html>""".encode())

# Запуск потоков
threading.Thread(target=fetch_market_data, daemon=True).start()
threading.Thread(target=save_to_db, daemon=True).start()
HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), WebHandler).serve_forever()
