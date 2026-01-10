import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

MONGO_URL = os.getenv("MONGO_URL")
# Список монет (можешь добавлять сюда новые)
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]

# Подключение к БД
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
    return {"date": today, "assets": {s: {"longs": 0.0, "shorts": 0.0, "exit": 0.0, "price": 0.0, "oi": 0.0, "action": "WAITING"} for s in SYMBOLS}}

session_data = load_data()

def monitor():
    global session_data
    prev_oi, prev_p = {}, {}
    while True:
        for s in SYMBOLS:
            try:
                res_p = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={s}", timeout=5).json()
                res_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                if 'price' not in res_p or 'openInterest' not in res_oi: continue
                
                p = float(res_p['price'])
                oi_count = float(res_oi['openInterest'])
                current_oi_usd = oi_count * p # Считаем OI в долларах
                
                if s in prev_oi:
                    d_oi = oi_count - prev_oi[s]
                    d_p = p - prev_p[s]
                    asset = session_data["assets"][s]
                    asset["price"] = p
                    asset["oi"] = current_oi_usd
                    
                    if d_oi > 0:
                        if d_p > 0: 
                            asset['longs'] += (d_oi * p)
                            asset['action'] = "🔥 AGRESSIVE BUY"
                        else: 
                            asset['shorts'] += (d_oi * p)
                            asset['action'] = "💀 AGRESSIVE SELL"
                    elif d_oi < 0:
                        val = abs(d_oi * p)
                        asset['exit'] += val
                        asset['action'] = "💧 EXIT/LIQUIDATION"
                    
                    collection.update_one({"date": session_data["date"]}, {"$set": session_data}, upsert=True)
                
                prev_oi[s], prev_p[s] = oi_count, p
            except: pass
        time.sleep(15)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        rows = ""
        for s, d in session_data["assets"].items():
            color = "#00ff88" if "BUY" in d['action'] else "#ff4444" if "SELL" in d['action'] else "#888"
            rows += f"""
            <tr>
                <td>{s}</td>
                <td>{d['price']:,.2f}</td>
                <td style='color:#00ff88;'>${d.get('longs',0):,.0f}</td>
                <td style='color:#ff4444;'>${d.get('shorts',0):,.0f}</td>
                <td style='color:#ffaa00;'>${d.get('exit',0):,.0f}</td>
                <td style='color:#00d9ff;'>${d.get('oi',0):,.0f}</td>
                <td style='color:{color}; font-weight:bold;'>{d['action']}</td>
            </tr>"""
            
        html = f"""
        <html>
        <head>
            <meta http-equiv='refresh' content='15'>
            <style>
                body {{ background: #050505; color: #eee; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; padding: 20px; }}
                table {{ border-collapse: collapse; width: 95%; max-width: 1000px; background: #111; border-radius: 10px; overflow: hidden; }}
                th {{ background: #222; padding: 15px; text-align: left; color: #888; font-size: 12px; }}
                td {{ padding: 15px; border-bottom: 1px solid #222; font-family: monospace; font-size: 14px; }}
                h1 {{ color: #00ff88; text-shadow: 0 0 10px rgba(0,255,136,0.3); }}
            </style>
        </head>
        <body>
            <h1>MARKET MONITOR v1.1</h1>
            <table>
                <tr>
                    <th>SYMBOL</th><th>PRICE</th><th>DAILY LONGS</th><th>DAILY SHORTS</th><th>DAILY EXITS</th><th>OPEN INTEREST</th><th>SIGNAL</th>
                </tr>
                {rows}
            </table>
        </body>
        </html>"""
        self.wfile.write(html.encode('utf-8'))

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
