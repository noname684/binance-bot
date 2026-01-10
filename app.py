import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

MONGO_URL = os.getenv("MONGO_URL")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]

# Подключение к БД
client = MongoClient(MONGO_URL)
db = client.market_monitor
collection = db.daily_stats

def load_data():
    today = datetime.now().strftime("%Y-%m-%d")
    data = collection.find_one({"date": today})
    if data: return data
    return {"date": today, "assets": {s: {"longs": 0.0, "shorts": 0.0, "exit": 0.0, "price": 0.0, "action": "WAITING"} for s in SYMBOLS}}

session_data = load_data()

def monitor():
    global session_data
    prev_oi, prev_p = {}, {}
    while True:
        for s in SYMBOLS:
            try:
                p = float(requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={s}").json()['price'])
                oi = float(requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}").json()['openInterest'])
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
                    else:
                        asset['exit'] += abs(d_oi * p)
                        asset['action'] = "💧 LIQUIDATION/EXIT"
                    collection.replace_one({"date": session_data["date"]}, session_data, upsert=True)
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
            rows += f"""
            <tr>
                <td style='padding:10px; border-bottom:1px solid #333;'>{s}</td>
                <td style='padding:10px; border-bottom:1px solid #333;'>{d['price']:.2f}</td>
                <td style='padding:10px; border-bottom:1px solid #333; color:#00ff88;'>${d['longs']:,.0f}</td>
                <td style='padding:10px; border-bottom:1px solid #333; color:#ff4444;'>${d['shorts']:,.0f}</td>
                <td style='padding:10px; border-bottom:1px solid #333; color:{color}; font-weight:bold;'>{d['action']}</td>
            </tr>
            """

        html = f"""
        <html>
        <head>
            <title>CRYPTO TERMINAL</title>
            <meta http-equiv="refresh" content="15">
            <style>
                body {{ background: #0a0a0a; color: #eee; font-family: 'Courier New', monospace; display: flex; flex-direction: column; align-items: center; padding-top: 50px; }}
                table {{ border-collapse: collapse; width: 80%; background: #111; border: 1px solid #333; box-shadow: 0 0 20px rgba(0,255,136,0.1); }}
                th {{ background: #1a1a1a; color: #888; text-align: left; padding
