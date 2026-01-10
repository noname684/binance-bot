import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "1000PEPEUSDT", "SUIUSDT", "XRPUSDT", "1000WHYUSDT"]
MONGO_URL = os.getenv("MONGO_URL")

# Инициализация хранилища
data_store = {s: {"p":0.0, "ls":0.0, "tb":0, "ts":0, "l":0, "sh":0, "ex":0, "liq":0, "oi":0} for s in SYMBOLS}
prev_data = {}

# Подключение к MongoDB
try:
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=2000)
    collection = client.market_monitor.daily_stats
    doc = collection.find_one({"date": datetime.now().strftime("%Y-%m-%d")})
    if doc and "assets" in doc:
        for s in SYMBOLS:
            if s in doc["assets"]:
                for key in ["l", "sh", "ex", "liq"]:
                    data_store[s][key] = doc["assets"][s].get(key, 0)
except: client = None

def fetch_data():
    global data_store, prev_data
    while True:
        try:
            # 1. ЗАПРОС ВСЕХ ЦЕН ОДНИМ ПАКЕТОМ (убирает OFFLINE)
            all_tickers = requests.get("https://fapi.binance.com/fapi/v1/ticker/price", timeout=5).json()
            prices = {t['symbol']: float(t['price']) for t in all_tickers if t['symbol'] in SYMBOLS}
            
            for s in SYMBOLS:
                if s not in prices: continue
                p = prices[s]
                
                # 2. Легкие запросы по каждой монете
                oi_data = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=3).json()
                ls_data = requests.get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={s}&period=5m&limit=1", timeout=3).json()
                vol_data = requests.get(f"https://fapi.binance.com/futures/data/takerbuybuyvol?symbol={s}&period=5m&limit=1", timeout=3).json()
                
                oi_usd = float(oi_data['openInterest']) * p
                tb = float(vol_data[0]['buyVol']) * p if vol_data else 0
                ts = (float(vol_data[0]['vol']) * p) - tb if vol_data else 0
                
                data_store[s].update({
                    "p": p, "ls": float(ls_data[0]['longShortRatio']) if ls_data else 0,
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
                time.sleep(1) # Пауза между монетами, чтобы не спамить
        except Exception as e:
            print(f"API Error: {e}")
        time.sleep(15) # Ждем 15 секунд перед следующим кругом

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
            p_str = f"{p:,.4f}" if p > 0 else "<span style='color:red;'>WAITING API...</span>"
            tb, ts = d['tb'], d['ts']
            pres = ((tb - ts) / (tb + ts) * 100) if (tb + ts) > 0 else 0
            
            rows += f"""<tr>
                <td style='color:#00ff88;'><b>{s}</b></td>
                <td style='font-family:monospace; font-size:18px;'>{p_str}</td>
                <td>{d['ls']:.2f}</td>
                <td style='color:{'#00ff88' if pres > 0 else '#ff4444'}; font-weight:bold;'>{pres:+.1f}%</td>
                <td style='color:#00ff88;'>${tb:,.0f}</td><td style='color:#ff4444;'>${ts:,.0f}</td>
                <td style='border-left:2px solid #333; color:#00ff88;'>${d['l']:,.0f}</td>
                <td style='color:#ff4444;'>${d['sh']:,.0f}</td>
                <td style='color:#ffaa00;'>${d['ex']:,.0f}</td>
                <td style='color:#00d9ff;'>${d['oi']:,.0f}</td>
            </tr>"""
        
        self.wfile.write(f"<html><head><meta http-equiv='refresh' content='15'><style>body{{background:#050505;color:#eee;font-family:sans-serif;padding:20px;}}table{{width:100%;border-collapse:collapse;}}th{{background:#111;padding:12px;color:#444;font-size:10px;text-align:left;}}td{{padding:12px;border-bottom:1px solid #181818;font-size:14px;}}</style></head><body><h1>WHALE RADAR v3.7 (STABLE)</h1><table><tr><th>Symbol</th><th>Price</th><th>L/S</th><th>Press (5m)</th><th>Taker Buy</th><th>Taker Sell</th><th style='border-left:2px solid #333;'>Longs (Day)</th><th>Shorts (Day)</th><th>Exits (Day)</th><th>OI USD</th></tr>{rows}</table></body></html>".encode())

threading.Thread(target=fetch_data, daemon=True).start()
threading.Thread(target=save_to_db, daemon=True).start()
HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), WebHandler).serve_forever()
