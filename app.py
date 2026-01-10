import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

MONGO_URL = os.getenv("MONGO_URL")
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
    return {"date": today, "assets": {s: {"longs": 0.0, "shorts": 0.0, "exit": 0.0, "price": 0.0, "action": "WAITING"} for s in SYMBOLS}}

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
                p, oi = float(res_p['price']), float(res_oi['openInterest'])
                if s in prev_oi:
                    d_oi, d_p = oi - prev_oi[s], p - prev_p[s]
                    asset = session_data["assets"][s]
                    asset["price"] = p
                    if d_oi > 0:
                        if d_p > 0: 
                            asset['longs'] += (d_oi * p)
                            asset['action'] = "🔥 AGRESSIVE BUY"
                        else: 
                            asset['shorts'] += (d_oi * p)
                            asset['action'] = "💀 AGRESSIVE SELL"
                    elif d_oi < 0:
                        asset['exit'] += abs(d_oi * p)
                        asset['action'] = "💧 LIQUIDATION/EXIT"
                    collection.update_one({"date": session_data["date"]}, {"$set": session_data}, upsert=True)
                prev_oi[s], prev_p[s] = oi, p
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
            rows += f"<tr><td style='padding:12px; border-bottom:1px solid #333;'>{s}</td><td style='padding:12px; border-bottom:1px solid #333;'>{d['price']:.2f}</td><td style='padding:12px; border-bottom:1px solid #333; color:#00ff88;'>${d['longs']:,.0f}</td><td style='padding:12px; border-bottom:1px solid #333; color:#ff4444;'>${d['shorts']:,.0f}</td><td style='padding:12px; border-bottom:1px solid #333; color:{color}; font-weight:bold;'>{d['action']}</td></tr>"
        html = f"<html><head><meta http-equiv='refresh' content='15'><style>body {{ background: #050505; color: #eee; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; padding: 40px; }} table {{ border-collapse: collapse; width: 90%; max-width: 800px; background: #111; }} th {{ background: #222; padding: 15px; text-align: left; }} h1 {{ color: #00ff88; }}</style></head><body><h1>MARKET MONITOR v1.0</h1><table><tr><th>SYMBOL</th><th>PRICE</th><th>LONGS</th><th>SHORTS</th><th>SIGNAL</th></tr>{rows}</table></body></html>"
        self.wfile.write(html.encode('utf-8'))

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
