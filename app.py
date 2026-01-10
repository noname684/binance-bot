import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

MONGO_URL = os.getenv("MONGO_URL")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "1000PEPEUSDT", "1000BONKUSDT", "SUIUSDT", "XRPUSDT"]

try:
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    db = client.market_monitor
    collection = db.daily_stats
except: pass

def load_data():
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        data = collection.find_one({"date": today})
        if data: return data
    except: pass
    return {"date": today, "assets": {s: {"longs": 0.0, "shorts": 0.0, "price": 0.0, "oi": 0.0, "vol": 0.0, "fund": 0.0, "power": 0, "action": "WAITING"} for s in SYMBOLS}}

session_data = load_data()

def monitor():
    global session_data
    prev_oi, prev_p = {}, {}
    while True:
        for s in SYMBOLS:
            try:
                r_t = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={s}", timeout=5).json()
                r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                r_f = requests.get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={s}", timeout=5).json()
                
                p = float(r_t['lastPrice'])
                vol_24h = float(r_t['quoteVolume'])
                oi_usd = float(r_oi['openInterest']) * p
                
                if s not in session_data["assets"]: session_data["assets"][s] = {"longs":0,"shorts":0,"price":0,"oi":0,"vol":0,"fund":0,"power":0,"action":"WAITING"}
                asset = session_data["assets"][s]
                asset.update({"price": p, "vol": vol_24h, "oi": oi_usd, "fund": float(r_f.get('lastFundingRate', 0)) * 100})

                if s in prev_oi:
                    d_oi = oi_usd - prev_oi[s]
                    d_p = p - prev_p[s]
                    
                    # КРИТИЧЕСКИЙ ПОРОГ: 0.05% от суточного объема за 15 секунд
                    threshold = vol_24h * 0.0005 
                    
                    if abs(d_oi) > threshold:
                        # Считаем силу сигнала (сколько порогов пробито)
                        power = int(abs(d_oi) / threshold)
                        asset['power'] = min(power, 10) # Максимум 10 "огней"
                        
                        if d_oi > 0:
                            if d_p > 0: asset['longs'] += d_oi; asset['action'] = "🔥" * asset['power'] + " BUY"
                            else: asset['shorts'] += d_oi; asset['action'] = "💀" * asset['power'] + " SELL"
                        else:
                            asset['action'] = "💧 EXIT"
                    else:
                        asset['power'] = 0
                
                prev_oi[s], prev_p[s] = oi_usd, p
            except: pass
        
        collection.update_one({"date": session_data["date"]}, {"$set": session_data}, upsert=True)
        time.sleep(15)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers()
        rows = ""
        for s, d in session_data["assets"].items():
            action = d.get('action', 'WAITING')
            clr = "#00ff88" if "BUY" in action else "#ff4444" if "SELL" in action else "#888"
            rows += f"<tr><td><b>{s}</b></td><td>{d.get('price',0):,.4f}</td><td>${d.get('vol',0):,.0f}</td><td style='color:#00ff88;'>${d.get('longs',0):,.0f}</td><td style='color:#ff4444;'>${d.get('shorts',0):,.0f}</td><td style='color:#00d9ff;'>${d.get('oi',0):,.0f}</td><td style='color:{clr}; font-weight:bold;'>{action}</td></tr>"
        
        self.wfile.write(f"<html><head><meta http-equiv='refresh' content='15'><style>body{{background:#050505;color:#eee;font-family:monospace;display:flex;flex-direction:column;align-items:center;padding:20px;}}table{{border-collapse:collapse;width:100%;max-width:1100px;background:#0a0a0a;border:1px solid #222;}}th{{background:#151515;padding:12px;text-align:left;color:#444;font-size:11px;}}td{{padding:12px;border-bottom:1px solid #111;font-size:13px;}}</style></head><body><h1>WHALE RADAR v1.7</h1><table><tr><th>SYMBOL</th><th>PRICE</th><th>24H VOL</th><th>DAILY LONGS</th><th>DAILY SHORTS</th><th>OI (USD)</th><th>SIGNAL</th></tr>{rows}</table></body></html>".encode())

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
