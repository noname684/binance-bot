import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

# Настройки активов
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
MONGO_URL = os.getenv("MONGO_URL")

# Подключение к базе данных
try:
    client = MongoClient(MONGO_URL)
    db = client.market_monitor
    collection = db.daily_stats
    print("--- [DATABASE] Connected to MongoDB Atlas ---")
except Exception as e:
    print(f"--- [DATABASE ERROR] {e} ---")

def load_from_db():
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        data = collection.find_one({"date": today})
        if data: return data
    except: pass
    # Если данных нет (новый день), создаем пустую структуру
    return {
        "date": today, 
        "assets": {s: {"longs": 0.0, "shorts": 0.0, "exit": 0.0, "price": 0.0, "oi": 0.0, "action": "WAITING", "last_delta": 0.0} for s in SYMBOLS}
    }

def save_to_db(data):
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        collection.replace_one({"date": today}, data, upsert=True)
    except: pass

# Загружаем данные при старте сервера
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
            td {{ padding: 12px 10px; border-bottom: 1px solid #151515; vertical-align: middle; }}
            .action-box {{ display: flex; flex-direction: column; align-items: flex-start; gap: 4px; }}
            .action-tag {{ padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 10px; text-transform: uppercase; }}
            .delta-val {{ font-size: 13px; font-weight: bold; font-family: monospace; }}
            .buy {{ color: #00ff88; }} .buy-bg {{ background: #004422; color: #00ff88; }}
            .sell {{ color: #ff4444; }} .sell-bg {{ background: #440011; color: #ff4444; }}
            .squeeze {{ color: #ffff00; }} .squeeze-bg {{ background: #444400; color: #ffff00; }}
            .flush {{ color: #ff8800; }} .flush-bg {{ background: #442200; color: #ff8800; }}
            .wait {{ color: #444; }}
        </style></head><body>
            <div class="header">
                <h1 style="margin:0; font-size: 24px; letter-spacing: 1px;">ORDERFLOW INTELLIGENCE</h1>
                <small style="color:#666;">DATE: {session_data['date']} | DATABASE: ONLINE | REFRESH: 15s</small>
            </div>
            <table>
                <tr>
                    <th>Asset / Price</th>
                    <th>Live Market Action ($ΔOI)</th>
                    <th>Daily Longs</th>
                    <th>Daily Shorts</th>
                    <th>Daily Exit 🚪</th>
                    <th>Total OI</th>
                </tr>
        """
        for s in SYMBOLS:
            a = assets.get(s, {})
            act = a.get('action', 'WAITING')
            delta = a.get('last_delta', 0)
            
            color_class, bg_class = "wait", ""
            if "BUY" in act: color_class, bg_class = "buy", "buy-bg"
            elif "SELL" in act: color_class, bg_class = "sell", "sell-bg"
            elif "SQUEEZE" in act: color_class, bg_class = "squeeze", "squeeze-bg"
            elif "FLUSH" in act: color_class, bg_class = "flush", "flush-bg"

            html += f"""
                <tr>
                    <td><b style="font-size:16px; color:#fff;">{s}</b><br><span style="color:#666; font-size:12px;">{a.get('price', 0):,.2f}$</span></td>
                    <td>
                        <div class="action-box">
                            <span class="action-tag {bg_class}">{act}</span>
                            <span class="delta-val {color_class}">{'+' if delta > 0 else ''}{format_currency(delta)}$</span>
                        </div>
                    </td>
                    <td style="color:#00ff88;">{format_currency(a.get('longs', 0))}$</td>
                    <td style="color:#ff4444;">{format_currency(a.get('shorts', 0))}$</td>
                    <td style="color:#ffa500;">{format_currency(a.get('exit', 0))}$</td>
                    <td style="color:#aaa; font-weight:bold;">${format_currency(a.get('oi', 0))}</td>
                </tr>
            """
        html += "</table></body></html>"
        self.wfile.write(html.encode('utf-8'))
    def log_message(self, format, *args): return

def monitor():
    global session_data
    prev_oi, prev_price = {}, {}
    print("--- [MONITOR] Orderflow tracking started ---")
    while True:
        # Проверка смены суток
        today = datetime.now().strftime("%Y-%m-%d")
        if session_data["date"] != today:
            session_data = load_from_db()

        for s in SYMBOLS:
            try:
                # Получаем цену и Open Interest
                r_p = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={s}", timeout=5).json()
                r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                
                p = float(r_p['price'])
                oi = float(r_oi['openInterest']) * p
                
                if s in prev_oi:
                    d_oi = oi - prev_oi[s]
                    d_p = p - prev_price[s]
                    
                    action = "WAITING"
                    if abs(d_p) > 0: # Если цена сдвинулась
                        if d_p > 0: action = "🔥 AGRESSIVE BUY" if d_oi > 0 else "⚡ SHORT SQUEEZE"
                        else: action = "💀 AGRESSIVE SELL" if d_oi > 0 else "💧 LONG FLUSH"
                    
                    # Обновляем состояние актива
                    asset_ref = session_data["assets"][s]
                    asset_ref.update({"price": p, "oi": oi, "action": action, "last_delta": d_oi})
                    
                    # Накопительная логика
                    if d_oi > 0:
                        if d_p > 0: asset_ref['longs'] += d_oi
                        else: asset_ref['shorts'] += d_oi
                    else:
                        asset_ref['exit'] += abs(d_oi)
                    
                    save_to_db(session_data)
                
                prev_oi[s], prev_price[s] = oi, p
            except: pass
        time.sleep(15)

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), SmartTerminal).serve_forever()
