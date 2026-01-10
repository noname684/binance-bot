import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

MONGO_URL = os.getenv("MONGO_URL")
# Добавил новые монеты в правильном формате
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "1000PEPEUSDT", "1000BONKUSDT", "SUIUSDT"]

try:
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    db = client.market_monitor
    collection = db.daily_stats
    print(">>> DATABASE CONNECTED", flush=True)
except:
    print(">>> DATABASE CONNECTION ERROR", flush=True)

def load_data():
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        data = collection.find_one({"date": today})
        if data: return data
    except: pass
    return {"date": today, "assets": {s: {"longs": 0.0, "shorts": 0.0, "liq": 0.0, "price": 0.0, "oi": 0.0, "vol": 0.0, "ratio": 1.0, "fund": 0.0, "action": "WAITING"} for s in SYMBOLS}}

session_data = load_data()

def monitor():
    global session_data
    prev_oi, prev_p = {}, {}
    while True:
        for s in SYMBOLS:
            try:
                # 1. Цена, объем и фандинг
                r_t = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={s}", timeout=5).json()
                r_f = requests.get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={s}", timeout=5).json()
                r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                
                if 'lastPrice' not in r_t or 'openInterest' not in r_oi: continue
                
                p = float(r_t['lastPrice'])
                oi_usd = float(r_oi['openInterest']) * p
                
                # Безопасное обновление данных актива
                if s not in session_data["assets"]:
                    session_data["assets"][s] = {"longs": 0.0, "shorts": 0.0, "liq": 0.0, "price": 0.0, "oi": 0.0, "vol": 0.0, "ratio": 1.0, "fund": 0.0, "action": "WAITING"}
                
                asset = session_data["assets"][s]
                asset["price"] = p
                asset["vol"] = float(r_t.get('quoteVolume', 0))
                asset["oi"] = oi_usd
                asset["fund"] = float(r_f.get('lastFundingRate', 0)) * 100
                
                if s in prev_oi:
                    d_oi = oi_usd - prev_oi[s]
                    d_p = p - prev_p[s]
                    if abs(d_oi) > 1000:
                        if d_oi > 0:
                            if d_p > 0: asset['longs'] += d_oi; asset['action'] = "🔥 BUY"
                            else: asset['shorts'] += d_oi; asset['action'] = "💀 SELL"
                        else:
                            asset['liq'] = asset.get('liq', 0) + abs(d_oi)
                            asset['action'] = "💧 EXIT"
                
                prev_oi[s], prev_p[s] = oi_usd, p
            except Exception as e:
                print(f"Error {s}: {e}", flush=True)
        
        try:
            collection.update_one({"date": session_data["date"]}, {"$set": session_data}, upsert=True)
        except: pass
        time.sleep(15)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        rows = ""
        for s, d in session_data["assets"].items():
            # Безопасное чтение через .get() во избежание KeyError
            fund = d.get('fund', 0)
            ratio = d.get('ratio', 1)
            action = d.get('action', 'WAITING')
            color = "#00ff88" if "BUY" in action else "#ff4444" if "SELL" in action else "#888"
            
            rows += f"""
            <tr>
                <td style='font-weight:bold;'>{s}</td>
                <td>{d.get('price', 0):,.4f}</td>
                <td style='color:#666;'>${d.get('vol', 0):,.0f}</td>
                <td style='color:#00ff88;'>${d.get('longs', 0):,.0f}</td>
                <td style='color:#ff4444;'>${d.get('shorts', 0):,.0f}</td>
                <td style='color:#888;'>{fund:.4f}%</td>
                <td style='color:#00d9ff;'>${d.get('oi', 0):,.0f}</td>
                <td style='background:#111; color:{color}; font-weight:bold;'>{action}</td>
            </tr>"""
        
        html = f"""
        <html><head><meta http-equiv='refresh' content='15'><style>
            body {{ background: #050505; color: #eee; font-family: 'Courier New', monospace; display: flex; flex-direction: column; align-items: center; padding: 20px; }}
            table {{ border-collapse: collapse; width: 100%; max-width: 1100px; background: #0a0a0a; border: 1px solid #222; }}
            th {{ background: #151515; padding: 12px; text-align: left; color: #444; font-size: 11px; }}
            td {{ padding: 12px; border-bottom: 1px solid #111; font-size: 13px; }}
            h1 {{ color: #00ff88; text-shadow: 0 0 10px #00ff8833; }}
        </style></head><body>
            <h1>WHALE TERMINAL v1.6</h1>
            <table>
                <tr><th>SYMBOL</th><th>PRICE</th><th>24H VOL</th><th>LONGS</th><th>SHORTS</th><th>FUNDING</th><th>OI (USD)</th><th>SIGNAL</th></tr>
                {rows}
            </table>
        </body></html>"""
        self.wfile.write(html.encode('utf-8'))

if __name__ == "__main__":
    t = threading.Thread(target=monitor, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
