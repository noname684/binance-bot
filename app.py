import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

MONGO_URL = os.getenv("MONGO_URL")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "1000PEPEUSDT", "SUIUSDT", "XRPUSDT", "1000WHYUSDT"]

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
    return {"date": today, "assets": {}}

session_data = load_data()

def monitor():
    global session_data
    prev_oi, prev_p = {}, {}
    while True:
        for s in SYMBOLS:
            try:
                r_t = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={s}", timeout=5).json()
                r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                r_ls = requests.get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={s}&period=5m&limit=1", timeout=5).json()
                
                p = float(r_t['lastPrice'])
                vol_24h = float(r_t['quoteVolume'])
                oi_usd = float(r_oi['openInterest']) * p
                ls_ratio = float(r_ls[0]['longShortRatio']) if r_ls else 0
                
                if s not in session_data["assets"]:
                    session_data["assets"][s] = {"longs":0.0, "shorts":0.0, "exit":0.0, "liq":0.0, "price":p, "ls":ls_ratio, "oi":oi_usd, "vol":vol_24h}
                
                asset = session_data["assets"][s]
                asset.update({"price": p, "ls": ls_ratio, "oi": oi_usd, "vol": vol_24h})

                if s in prev_oi:
                    d_oi = oi_usd - prev_oi[s]
                    d_p = p - prev_p[s]
                    
                    if d_oi > 0:
                        if d_p >= 0: asset['longs'] += d_oi
                        else: asset['shorts'] += d_oi
                    else:
                        asset['exit'] += abs(d_oi)
                        if abs(d_p/p) > 0.001: asset['liq'] += abs(d_oi)
                
                prev_oi[s], prev_p[s] = oi_usd, p
            except: pass
        
        collection.update_one({"date": session_data["date"]}, {"$set": session_data}, upsert=True)
        time.sleep(10)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers()
        rows = ""
        for s in SYMBOLS:
            d = session_data["assets"].get(s, {})
            ls = d.get('ls', 0)
            ls_clr = "#ff4444" if ls > 1.8 else "#00ff88" if ls < 0.8 else "#aaa"
            
            # Расчет Pressure (Дисбаланс входов)
            l, sh = d.get('longs', 0), d.get('shorts', 0)
            total = l + sh
            pressure = ((l - sh) / total * 100) if total > 0 else 0
            pres_clr = "#00ff88" if pressure > 20 else "#ff4444" if pressure < -20 else "#555"

            price = d.get('price', 0)
            p_str = f"{price:,.8f}" if price < 0.01 else f"{price:,.4f}" if price < 100 else f"{price:,.2f}"

            rows += f"""<tr>
                <td style='color:#00ff88; font-size:18px;'><b>{s}</b></td>
                <td style='font-family:monospace;'>{p_str}</td>
                <td style='color:{ls_clr}; font-weight:bold;'>{ls:.2f}</td>
                <td style='color:{pres_clr}; font-weight:bold;'>{pressure:+.1f}%</td>
                <td style='color:#777;'>${d.get('vol',0):,.0;f}</td>
                <td style='color:#00ff88;'>${l:,.0f}</td>
                <td style='color:#ff4444;'>${sh:,.0f}</td>
                <td style='color:#ffaa00;'>${d.get('exit',0):,.0f}</td>
                <td style='color:#ff0055; background:rgba(255,0,85,0.05);'>${d.get('liq',0):,.0f}</td>
                <td style='color:#00d9ff;'>${d.get('oi',0):,.0f}</td>
            </tr>"""
        
        self.wfile.write(f"""<html><head><meta http-equiv='refresh' content='10'><style>
            body {{ background:#050505; color:#eee; font-family:sans-serif; padding:20px; }}
            table {{ border-collapse:collapse; width:100%; max-width:1600px; background:#0a0a0a; }}
            th {{ background:#111; padding:15px; color:#444; font-size:10px; text-align:left; border-bottom:2px solid #222; }}
            td {{ padding:15px; border-bottom:1px solid #111; font-size:15px; }}
        </style></head><body>
            <h1>WHALE TERMINAL v2.8</h1>
            <table>
                <tr>
                    <th>SYMBOL</th><th>PRICE</th><th>L/S RATIO</th><th>PRESSURE</th><th>24H VOLUME</th>
                    <th>LONGS (IN)</th><th>SHORTS (IN)</th><th>EXITS (OUT)</th><th>LIQ</th><th>OPEN INTEREST</th>
                </tr>
                {rows}
            </table>
        </body></html>""".encode())

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
