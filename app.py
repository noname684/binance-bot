import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
MONGO_URL = os.getenv("MONGO_URL")

try:
    client = MongoClient(MONGO_URL)
    db = client.market_monitor
    collection = db.daily_stats
except Exception as e:
    print(f"DB Error: {e}")

def load_from_db():
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        data = collection.find_one({"date": today})
        if data: return data
    except: pass
    return {"date": today, "assets": {s: {"longs": 0.0, "shorts": 0.0, "exit": 0.0, "price": 0.0, "oi": 0.0, "oi_coins": 0.0, "action": "WAITING", "last_delta": 0.0, "coin_delta": 0.0} for s in SYMBOLS}}

def save_to_db(data):
    today = datetime.now().strftime("%Y-%m-%d")
    try: collection.replace_one({"date": today}, data, upsert=True)
    except: pass

session_data = load_from_db()

def format_currency(value):
    abs_val = abs(value)
    if abs_val >= 1_000_000_000: return f"{value / 1_000_000_000:.2f}B"
    elif abs_val >= 1_000_000: return f"{value / 1_000_000:.2f}M"
    elif abs_val >= 1_000: return f"{value / 1_000:.1f}k"
    return f"{value:.2f}"

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
            th {{ text-align: left; color: #444; font-size: 11px; text-transform: uppercase; padding: 10px; border-bottom: 2px solid #222; }}
            td {{ padding: 12px 10px; border-bottom: 1px solid #151515; }}
            .action-tag {{ padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 10px; }}
            .delta-coin {{ font-size: 11px; color: #888; font-family: monospace; }}
            .buy {{ color: #00ff88; }} .buy-bg {{ background: #004422; color: #00ff88; }}
            .sell {{ color: #ff4444; }} .sell-bg {{ background: #440011; color: #ff4444; }}
            .squeeze {{ color: #ffff00; }} .squeeze-bg {{ background: #444400; color: #ffff00; }}
            .flush {{ color: #ff8800; }} .flush-bg {{ background: #442200; color: #ff8800; }}
        </style></head><body>
            <div class="header">
                <h1 style="margin:0;">ORDERFLOW & BORROW MONITOR</h1>
                <small style="color:#666;">DATABASE: ONLINE | REFRESH: 15s</small>
            </div>
            <table>
                <tr>
                    <th>Asset / Price</th>
                    <th>Action & Coin Borrow (Δ)</th>
                    <th>Daily Longs</th>
                    <th>Daily Shorts</th>
                    <th>Total OI (Coins)</th>
                </tr>
        """
        for s in SYMBOLS:
            a = assets.get(s, {})
            act = a.get('action', 'WAITING')
            d_coin = a.get('coin_delta', 0)
            coin_name = s.replace("USDT", "")
            
            cls, bg = ("buy", "buy-bg") if "BUY" in act else ("sell", "sell-bg") if "SELL" in act else ("squeeze", "squeeze-bg") if "SQUEEZE" in act else ("flush", "flush-bg") if "FLUSH" in act else ("wait", "")

            html += f"""
                <tr>
                    <td><b style="font-size:16px;">{s}</b><br><small style="color:#666;">{a.get('price', 0):,.2f}$</small></td>
                    <td>
                        <span class="action-tag {bg}">{act}</span><br>
                        <span class="delta-coin {cls}">{'↑' if d_coin > 0 else '↓' if d_coin < 0 else ''} {abs(d_coin):,.3f} {coin_name}</span>
                    </td>
                    <td style="color:#00ff88;">{format_currency(a.get('longs', 0))}$</td>
                    <td style="color:#ff4444;">{format_currency(a.get('shorts', 0))}$</td>
                    <td>
                        <b style="color:#fff;">${format_currency(a.get('oi', 0))}</b><br>
                        <small style="color:#666;">{a.get('oi_coins', 0):,.2f} {coin_name}</small>
                    </td>
                </tr>
            """
        html += "</table></body></html>"
        self.wfile.write(html.encode('utf-8'))

def monitor():
    global session_data
    prev_oi_coins, prev_price = {}, {}
    while True:
        for s in SYMBOLS:
            try:
                r_p = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={s}", timeout=5).json()
                r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                
                p = float(r_p['price'])
                oi_coins = float(r_oi['openInterest'])
                oi_usd = oi_coins * p
                
                if s in prev_oi_coins:
                    d_coins = oi_coins - prev_oi_coins[s]
                    d_p = p - prev_price[s]
                    
                    action = "WAITING"
                    if d_p > 0: action = "🔥 AGRESSIVE BUY" if d_coins > 0 else "⚡ SHORT SQUEEZE"
                    elif d_p < 0: action = "💀 AGRESSIVE SELL" if d_coins > 0 else "💧 LONG FLUSH"
                    
                    asset_ref = session_data["assets"][s]
                    asset_ref.update({"price": p, "oi": oi_usd, "oi_coins": oi_coins, "action": action, "coin_delta": d_coins})
                    
                    # Накопление
                    if d_coins > 0:
                        if d_p > 0: asset_ref['longs'] += (d_coins * p)
                        else: asset_ref['shorts'] += (d_coins * p)
                    else: asset_ref['exit'] += abs(d_coins * p)
                    
                    save_to_db(session_data)
                
                prev_oi_coins[s], prev_price[s] = oi_coins, p
            except: pass
        time.sleep(15)

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), SmartTerminal).serve_forever()
