import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

MONGO_URL = os.getenv("MONGO_URL")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]

# Подключение к БД с обработкой ошибок
try:
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    db = client.market_monitor
    collection = db.daily_stats
    client.admin.command('ping')
    print(">>> DATABASE CONNECTED!", flush=True)
except Exception as e:
    print(f">>> DATABASE CONNECTION ERROR: {e}", flush=True)

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
    print(">>> MONITORING STARTED", flush=True)
    while True:
        for s in SYMBOLS:
            try:
                # Запросы к Binance с проверкой ответов
                res_p = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={s}", timeout=5).json()
                res_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                
                if 'price' not in res_p or 'openInterest' not in res_oi:
                    continue

                p = float(res_p['price'])
                oi = float(res_oi['openInterest'])
                
                if s in prev_oi:
                    d_oi = oi - prev_oi[s]
                    d_p = p - prev_p[s]
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
                    
                    # Сохранение в БД
                    collection.update_one({"date": session_data["date"]}, {"$set": session_data}, upsert=True)
                
                prev_oi[s], prev_p[s] = oi, p
            except Exception as e:
                print(f">>> LOOP ERROR ON {s}: {e}", flush=True)
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
                <td style='padding:12px; border-bottom:1px solid #333;'>{s}</td>
                <td style='padding:12px; border-bottom:1px solid #333;'>{d['price']:,.2f}</td>
                <td style='padding:12px; border-bottom:1px solid #333; color:#00ff88;'>${d['longs']:,.0f}</td>
                <td style='padding:12px; border-bottom:1px solid #333; color:#ff4444;'>${d['shorts']:,.0f}</td>
                <td style='padding:12px; border-bottom:1px solid #333; color:{color}; font-weight:bold;'>{d['action']}</td>
            </tr>"""

        html = f"""
        <html>
        <head>
            <title>CRYPTO TERMINAL</title>
            <meta http-equiv="refresh" content="15">
            <style>
                body {{ background: #050505; color: #eee; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; padding: 40px; }}
                table {{ border-collapse: collapse; width: 90%; max-width: 900px; background: #111; border-radius: 8px; overflow: hidden; }}
                th {{ background: #222; color: #aaa; text-align: left; padding: 15px; font-size: 12px; letter-spacing: 1px; }}
                h1 {{ color: #00ff88; letter-spacing: 2px; margin-bottom: 5px; }}
                .status {{ margin-bottom: 30px; color: #555; font-size: 14px; }}
            </style>
        </head>
        <body>
            <h1>MARKET MONITOR v1.0</h1>
            <div class="status">LIVE FEED | DATE: {session_data['date']} | STATUS: CONNECTED</div>
            <table>
                <tr><th>SYMBOL</th><th>PRICE</th><th>DAILY LONGS</th><th>DAILY SHORTS</th><th>SIGNAL</th></tr>
                {rows}
            </table>
        </body>
        </html>"""
        self.wfile.
