import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

MONGO_URL = os.getenv("MONGO_URL")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "1000PEPEUSDT", "SUIUSDT", "XRPUSDT", "1000WHYUSDT"]

try:
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    db = client.market_monitor
    collection = db.daily_stats
except: pass

def load_data():
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        data = collection.find_one({"date": today})
        if data: return data
    except: pass
    return {"date": today, "assets": {}}

session_data = load_data()

def monitor():
    global session_data
    prev_oi, prev_p = {}, {}
    while True:
        for s in SYMBOLS:
            try:
                # 1. Основные данные (OI, Price, LS Ratio)
                r_t = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={s}", timeout=5).json()
                r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                r_ls = requests.get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={s}&period=5m&limit=1", timeout=5).json()
                
                # 2. ДАННЫЕ ПО РЕАЛЬНЫМ РЫНОЧНЫМ УДАРАМ (Taker Volume)
                r_dv = requests.get(f"https://fapi.binance.com/futures/data/takerbuybuyvol?symbol={s}&period=5m&limit=1", timeout=5).json()
                
                p = float(r_t['lastPrice'])
                oi_usd = float(r_oi['openInterest']) * p
                ls_ratio = float(r_ls[0]['longShortRatio']) if r_ls else 0
                
                # Считаем Дельту (Покупки минус Продажи по рынку)
                if r_dv:
                    mkt_buy = float(r_dv[0]['buyVol']) * p
                    mkt_sell = (float(r_dv[0]['vol']) * p) - mkt_buy
                    mkt_delta = mkt_buy - mkt_sell
                else:
                    mkt_delta = 0

                if s not in session_data["assets"]:
                    session_data["assets"][s] = {"longs":0, "shorts":0, "exit":0, "liq":0, "mkt_delta":0}
                
                asset = session_data["assets"][s]
                asset.update({"price": p, "ls": ls_ratio, "oi": oi_usd, "vol": float(r_t['quoteVolume']), "mkt_delta": mkt_delta})

                if s in prev_oi:
                    d_oi = oi_usd - prev_oi[s]
                    d_p = p - prev_p[s]
                    
                    if d_oi > 0:
                        if d_p >= 0: asset['longs'] += d_oi
                        else: asset['shorts'] += d_oi
                    else:
                        asset['exit'] += abs(d_oi)
                        if abs(d_p/p) > 0.0015: asset['liq'] += abs(d_oi)
                
                prev_oi[s], prev_p[s] = oi_usd, p
            except Exception as e:
                print(f"Error {s}: {e}")
        
        collection.update_one({"date": session_data["date"]}, {"$set": session_data}, upsert=True)
        time.sleep(10)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers()
        rows = ""
        for s in SYMBOLS:
            d = session_data["assets"].get(s, {})
            if not d: continue
            
            delta = d.get('mkt_delta', 0)
            d_clr = "#00ff88" if delta > 0 else "#ff4444"
            
            ls = d.get('ls', 0)
            ls_clr = "#ff4444" if ls > 1.8 else "#00ff88" if ls < 0.8 else "#aaa"

            rows += f"""<tr>
                <td style='color:#00ff88; font-size:18px;'><b>{s}</b></td>
                <td style='font-family:monospace;'>{d.get('price',0):,.4f}</td>
                <td style='color:{ls_clr}; font-weight:bold;'>{ls:.2f}</td>
                <td style='color:{d_clr}; font-weight:bold; background:rgba(0,0,0,0.3);'>${delta:,.0f}</td>
                <td style='color:#666;'>${d.get('vol',0):,.0f}</td>
                <td style='color:#00ff88;'>${d.get('longs',0):,.0f}</td>
                <td style='color:#ff4444;'>${d.get('shorts',0):,.0f}</td>
                <td style='color:#ffaa00;'>${d.get('exit',0):,.0f}</td>
                <td style='color:#ff0055;'>${d.get('liq',0):,.0f}</td>
                <td style='color:#00d9ff;'>${d.get('oi',0):,.0f}</td>
            </tr>"""
        
        html = f"""<html><head><meta http-equiv='refresh' content='10'><style>
            body {{ background:#050505; color:#eee; font-family:sans-serif; padding:15px; }}
            table {{ border-collapse:collapse; width:100%; max-width:1600px; background:#0a0a0a; }}
            th {{ background:#111; padding:12px; color:#444; font-size:10px; text-align:left; }}
            td {{ padding:15px; border-bottom:1px solid #181818; font-size:14px; }}
        </style></head><body>
            <h1>WHALE RADAR v3.1 (NET DELTA)</h1>
            <table>
                <tr><th>SYMBOL</th><th>PRICE</th><th>L/S RATIO</th><th>MKT DELTA (5m)</th><th>24H VOL</th><th>LONGS (OI)</th><th>SHORTS (OI)</th><th>EXITS</th><th>LIQ</th><th>OI USD</th></tr>
                {rows}
            </table>
        </body></html>"""
        self.wfile.write(html.encode())

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
