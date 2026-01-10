import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

# Настройки
MONGO_URL = os.getenv("MONGO_URL")
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

# Твой актуальный список (добавляй/удаляй здесь)
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "1000PEPEUSDT", "SUIUSDT", "XRPUSDT"]

try:
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    db = client.market_monitor
    collection = db.daily_stats
except: pass

def send_tg(msg):
    if TG_TOKEN and TG_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
            requests.post(url, data={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
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
                r_t = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={s}", timeout=5).json()
                r_f = requests.get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={s}", timeout=5).json()
                r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                
                p = float(r_t['lastPrice'])
                vol_24h = float(r_t['quoteVolume'])
                oi_usd = float(r_oi['openInterest']) * p
                
                if s not in session_data["assets"]:
                    session_data["assets"][s] = {"longs": 0.0, "shorts": 0.0, "exit": 0.0, "price": 0.0, "oi": 0.0, "vol": 0.0, "fund": 0.0, "action": "WAITING"}
                
                asset = session_data["assets"][s]
                asset.update({"price": p, "vol": vol_24h, "oi": oi_usd, "fund": float(r_f.get('lastFundingRate', 0)) * 100})

                if s in prev_oi:
                    d_oi = oi_usd - prev_oi[s]
                    d_p = p - prev_p[s]
                    threshold = vol_24h * 0.001 # Порог 0.1%
                    
                    if abs(d_oi) > threshold:
                        power = int(abs(d_oi) / threshold)
                        fires = "🔥" * min(power, 5)
                        if d_oi > 0:
                            type_sig = "BUY" if d_p > 0 else "SELL"
                            asset['action'] = f"{fires} {type_sig}"
                            if d_p > 0: asset['longs'] += d_oi 
                            else: asset['shorts'] += d_oi
                            if power >= 2:
                                send_tg(f"{fires} <b>{s} SIGNAL</b>\nPrice: {p}\nFlow: ${d_oi:,.0f}\nFund: {asset['fund']:.4f}%")
                        else:
                            asset['exit'] += abs(d_oi)
                            asset['action'] = "💧 EXIT"
                    else: asset['action'] = "WAITING"
                
                prev_oi[s], prev_p[s] = oi_usd, p
            except: pass
        collection.update_one({"date": session_data["date"]}, {"$set": session_data}, upsert=True)
        time.sleep(15)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers()
        rows = ""
        # ФИЛЬТР: Берем только монеты из списка SYMBOLS
        for s in SYMBOLS:
            d = session_data["assets"].get(s)
            if not d: continue # Если данных по монете еще нет, пропускаем её
            
            action = d.get('action', 'WAITING')
            clr = "#00ff88" if "BUY" in action else "#ff4444" if "SELL" in action else "#ffaa00" if "EXIT" in action else "#555"
            fund_val = d.get('fund', 0)
            fund_clr = "#ff4444" if fund_val > 0.03 else "#00ff88" if fund_val < 0 else "#888"

            rows += f"""<tr>
                <td><b>{s}</b></td>
                <td>{d.get('price',0):,.4f}</td>
                <td style='color:{fund_clr};'>{fund_val:.4f}%</td>
                <td style='color:#666;'>${d.get('vol',0):,.0f}</td>
                <td style='color:#00ff88;'>${d.get('longs',0):,.0f}</td>
                <td style='color:#ff4444;'>${d.get('shorts',0):,.0f}</td>
                <td style='color:#ffaa00;'>${d.get('exit',0):,.0f}</td>
                <td style='color:#00d9ff;'>${d.get('oi',0):,.0f}</td>
                <td style='color:{clr}; font-weight:bold;'>{action}</td>
            </tr>"""
        
        self.wfile.write(f"""<html><head><meta http-equiv='refresh' content='15'><style>
            body{{background:#050505;color:#eee;font-family:monospace;display:flex;flex-direction:column;align-items:center;padding:10px;}}
            table{{border-collapse:collapse;width:100%;max-width:1300px;background:#0a0a0a;border:1px solid #222;}}
            th{{background:#151515;padding:10px;text-align:left;color:#444;font-size:10px;}}
            td{{padding:12px;border-bottom:1px solid #111;font-size:12px;}}
            h1{{color:#00ff88;font-size:18px;}}
        </style></head><body>
            <h1>WHALE TERMINAL v2.0</h1>
            <table>
                <tr><th>SYMBOL</th><th>PRICE</th><th>FUNDING</th><th>24H VOL</th><th>LONGS</th><th>SHORTS</th><th>EXITS</th><th>OI (USD)</th><th>SIGNAL</th></tr>
                {rows}
            </table>
        </body></html>""".encode())

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
