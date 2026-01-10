import requests, time, threading, os, json
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
MONGO_URL = os.getenv("MONGO_URL", "твой_url")

try:
    client = MongoClient(MONGO_URL)
    db = client.market_monitor
    collection = db.daily_stats
except: pass

def load_from_db():
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        data = collection.find_one({"date": today})
        if data: return data
    except: pass
    return {"date": today, "assets": {s: {"longs": 1.0, "shorts": 1.0, "exit": 0, "price": 0, "oi": 0, "action": "WAITING"} for s in SYMBOLS}}

def save_to_db(data):
    today = datetime.now().strftime("%Y-%m-%d")
    try: collection.replace_one({"date": today}, data, upsert=True)
    except: pass

session_data = load_from_db()

def format_currency(value):
    abs_val = abs(value)
    if abs_val >= 1_000_000_000: return f"{value / 1_000_000_000:.2f}B"
    elif abs_val >= 1_000_000: return f"{value / 1_000_000:.2f}M"
    return f"{value:.0f}"

class SmartTerminal(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        assets = session_data["assets"]
        html = f"""
        <html><head><meta http-equiv="refresh" content="15">
        <style>
            body {{ background: #050505; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; padding: 20px; }}
            .header {{ background: #111; padding: 20px; border-radius: 12px; border-left: 8px solid #00ff88; margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th {{ text-align: left; color: #444; font-size: 12px; padding: 10px; border-bottom: 2px solid #222; }}
            td {{ padding: 15px 10px; border-bottom: 1px solid #151515; }}
            .action-tag {{ padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }}
            .buy {{ background: #004422; color: #00ff88; }}
            .sell {{ background: #440011; color: #ff4444; }}
            .squeeze {{ background: #444400; color: #ffff00; }}
            .flush {{ background: #442200; color: #ff8800; }}
        </style></head><body>
            <div class="header">
                <h1 style="margin:0;">SMART ORDERFLOW TERMINAL</h1>
                <small style="color:#666;">DB: ONLINE | MONITORING {len(SYMBOLS)} ASSETS</small>
            </div>
            <table>
                <tr>
                    <th>ASSET / PRICE</th>
                    <th>MARKET ACTION</th>
                    <th>DAILY LONGS</th>
                    <th>DAILY SHORTS</th>
                    <th>TOTAL OI</th>
                </tr>
        """
        for s in SYMBOLS:
            a = assets[s]
            act = a.get('action', 'NEUTRAL')
            cls = "buy" if "BUY" in act else "sell" if "SELL" in act else "squeeze" if "SQUEEZE" in act else "flush"
            
            html += f"""
                <tr>
                    <td><b style="font-size:18px; color:#fff;">{s}</b><br><span style="color:#666;">{a['price']:,.2f}$</span></td>
                    <td><span class="action-tag {cls}">{act}</span></td>
                    <td style="color:#00ff88;">{format_currency(a['longs'])}$</td>
                    <td style="color:#ff4444;">{format_currency(a['shorts'])}$</td>
                    <td style="color:#aaa; font-weight:bold;">${format_currency(a['oi'])}</td>
                </tr>
            """
        html += "</table></body></html>"
        self.wfile.write(html.encode('utf-8'))
    def log_message(self, format, *args): return

def monitor():
    global session_data
    prev_oi = {}
    prev_price = {}
    while True:
        for s in SYMBOLS:
            try:
                r_p = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={s}", timeout=5).json()
                r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                p = float(r_p['price'])
                oi = float(r_oi['openInterest']) * p
                
                if s in prev_oi and s in prev_price:
                    d_oi = oi - prev_oi[s]
                    d_p = p - prev_price[s]
                    
                    # Логика определения действия
                    action = "WAITING"
                    if d_p > 0 and d_oi > 10000: action = "🔥 AGRESSIVE BUY"
                    elif d_p > 0 and d_oi < -10000: action = "⚡ SHORT SQUEEZE"
                    elif d_p < 0 and d_oi > 10000: action = "💀 AGRESSIVE SELL"
                    elif d_p < 0 and d_oi < -10000: action = "💧 LONG FLUSH"
                    
                    session_data["assets"][s].update({"price": p, "oi": oi, "action": action})
                    
                    if d_oi > 20000: session_data["assets"][s]['longs'] += d_oi
                    elif d_oi < -20000: session_data["assets"][s]['shorts'] += abs(d_oi)
                    
                    save_to_db(session_data)
                
                prev_oi[s] = oi
                prev_price[s] = p
            except: pass
        time.sleep(15)

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    HTTPServer(('0.0.0.0', 10000), SmartTerminal).serve_forever()
