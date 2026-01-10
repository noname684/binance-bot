import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

MONGO_URL = os.getenv("MONGO_URL")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]

try:
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    db = client.market_monitor
    collection = db.daily_stats
    print(">>> DATABASE CONNECTED!", flush=True)
except Exception as e:
    print(f">>> DATABASE ERROR: {e}", flush=True)

def load_data():
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        data = collection.find_one({"date": today})
        if data: return data
    except: pass
    return {"date": today, "assets": {s: {"longs": 0.0, "shorts": 0.0, "exit": 0.0, "price": 0.0, "oi": 0.0, "vol": 0.0, "ratio": 0.0, "fund": 0.0, "liq": 0.0, "action": "WAITING"} for s in SYMBOLS}}

session_data = load_data()

def monitor():
    global session_data
    prev_oi, prev_p = {}, {}
    while True:
        for s in SYMBOLS:
            try:
                # 1. Цена, Объем и Фандинг
                r_t = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={s}", timeout=5).json()
                r_f = requests.get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={s}", timeout=5).json()
                
                # 2. Open Interest
                r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                
                # 3. Long/Short Ratio (Топ трейдеры по позициям)
                r_ls = requests.get(f"https://fapi.binance.com/fapi/v1/data/topLongShortAccountRatio?symbol={s}&period=5m&limit=1", timeout=5).json()

                if 'lastPrice' not in r_t or 'openInterest' not in r_oi: continue
                
                p = float(r_t['lastPrice'])
                oi_c = float(r_oi['openInterest'])
                asset = session_data["assets"][s]
                
                asset["price"] = p
                asset["vol"] = float(r_t['quoteVolume'])
                asset["oi"] = oi_c * p
                asset["fund"] = float(r_f.get('lastFundingRate', 0)) * 100 # в процентах
                if r_ls: asset["ratio"] = float(r_ls[0]['longShortRatio'])
                
                if s in prev_oi:
                    d_oi = oi_c - prev_oi[s]
                    d_p = p - prev_p[s]
                    if d_oi > 0:
                        if d_p > 0: asset['longs'] += (d_oi * p); asset['action'] = "🔥 BUY"
                        else: asset['shorts'] += (d_oi * p); asset['action'] = "💀 SELL"
                    elif d_oi < 0:
                        asset['exit'] += abs(d_oi * p); asset['action'] = "💧 EXIT"
                    
                    collection.update_one({"date": session_data["date"]}, {"$set": session_data}, upsert=True)
                
                prev_oi[s], prev_p[s] = oi_c, p
            except Exception as e: print(f"Err {s}: {e}")
        time.sleep(15)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers()
        rows = ""
        for s, d in session_data["assets"].items():
            f_clr = "#ff4444" if d['fund'] > 0.02 else "#00ff88" if d['fund'] < 0 else "#888"
            r_clr = "#ff4444" if d['ratio'] > 2.0 else "#00ff88" if d['ratio'] < 0.8 else "#ccc"
            rows += f"""
            <tr>
                <td style='font-weight:bold;'>{s}</td>
                <td>{d['price']:,.2f}</td>
                <td style='color:#666;'>${d['vol']:,.0f}</td>
                <td style='color:#00ff88;'>${d['longs']:,.0f}</td>
                <td style='color:#ff4444;'>${d['shorts']:,.0f}</td>
                <td style='color:{f_clr};'>{d['fund']:.4f}%</td>
                <td style='color:{r_clr};'>{d['ratio']:.2f}</td>
                <td style='color:#00d9ff;'>${d['oi']:,.0f}</td>
                <td style='background:#222; font-weight:bold; color:{"#00ff88" if "BUY" in d['action'] else "#ff4444" if "SELL" in d['action'] else "#888"}'>{d['action']}</td>
            </tr>"""
        
        self.wfile.write(f"""
        <html><head><meta http-equiv='refresh' content='15'><style>
            body {{ background: #050505; color: #eee; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; padding: 20px; }}
            table {{ border-collapse: collapse; width: 100%; max-width: 1200px; background: #111; }}
            th {{ background: #1a1a1a; padding: 12px; text-align: left; color: #555; font-size: 10px; }}
            td {{ padding: 12px; border-bottom: 1px solid #222; font-family: monospace; font-size: 12px; }}
            h1 {{ color: #00ff88; text-shadow: 0 0 10px rgba(0,255,136,0.2); }}
        </style></head><body>
            <h1>CRYPTO WHALE TERMINAL v1.3</h1>
            <table>
                <tr><th>SYMBOL</th><th>PRICE</th><th>24H VOL</th><th>DAILY LONGS</th><th>DAILY SHORTS</th><th>FUNDING</th><th>L/S RATIO</th><th>OI (USD)</th><th>SIGNAL</th></tr>
                {rows}
            </table>
        </body></html>""".encode())

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
