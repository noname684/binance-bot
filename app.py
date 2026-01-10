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
                # 1. Данные по OI и Цене
                r_t = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={s}", timeout=5).json()
                r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                r_ls = requests.get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={s}&period=5m&limit=1", timeout=5).json()
                
                # 2. Данные по Тейкерам (Market Orders)
                r_dv = requests.get(f"https://fapi.binance.com/futures/data/takerbuybuyvol?symbol={s}&period=5m&limit=1", timeout=5).json()
                
                p = float(r_t['lastPrice'])
                oi_usd = float(r_oi['openInterest']) * p
                ls_ratio = float(r_ls[0]['longShortRatio']) if r_ls else 0
                
                if r_dv:
                    t_buy = float(r_dv[0]['buyVol']) * p
                    t_sell = (float(r_dv[0]['vol']) * p) - t_buy
                else: t_buy = t_sell = 0

                if s not in session_data["assets"]:
                    session_data["assets"][s] = {"longs":0, "shorts":0, "exit":0, "liq":0, "t_buy":0, "t_sell":0}
                
                asset = session_data["assets"][s]
                asset.update({"price": p, "ls": ls_ratio, "oi": oi_usd, "vol": float(r_t['quoteVolume']), "t_buy": t_buy, "t_sell": t_sell})

                if s in prev_oi:
                    d_oi = oi_usd - prev_oi[s]
                    d_p = p - prev_p[s]
                    
                    if d_oi > 0:
                        if d_p >= 0: asset['longs'] += d_oi
                        else: asset['shorts'] += d_oi
                    else:
                        asset['exit'] += abs(d_oi)
                        if abs(d_p/p) > 0.0015: asset['liq'] += abs(d_oi)
                
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
            if not d: continue
            
            ls = d.get('ls', 0)
            ls_clr = "#ff4444" if ls > 1.8 else "#00ff88" if ls < 0.8 else "#aaa"
            
            tb, ts = d.get('t_buy',0), d.get('t_sell',0)
            pressure = ((tb - ts) / (tb + ts) * 100) if (tb + ts) > 0 else 0
            p_clr = "#00ff88" if pressure > 15 else "#ff4444" if pressure < -15 else "#888"

            rows += f"""<tr>
                <td style='color:#00ff88; font-size:16px;'><b>{s}</b></td>
                <td style='font-family:monospace;'>{d.get('price',0):,.4f}</td>
                <td style='color:{ls_clr}; font-weight:bold;'>{ls:.2f}</td>
                <td style='color:{p_clr}; font-weight:bold;'>{pressure:+.1f}%</td>
                <td style='color:#00ff88; background:rgba(0,255,136,0.05);'>${tb:,.0f}</td>
                <td style='color:#ff4444; background:rgba(255,68,68,0.05);'>${ts:,.0f}</td>
                <td style='border-left:2px solid #333; color:#00ff88;'>${d.get('longs',0):,.0f}</td>
                <td style='color:#ff4444;'>${d.get('shorts',0):,.0f}</td>
                <td style='color:#ffaa00;'>${d.get('exit',0):,.0f}</td>
                <td style='color:#ff0055;'>${d.get('liq',0):,.0f}</td>
                <td style='color:#00d9ff;'>${d.get('oi',0):,.0f}</td>
                <td style='color:#555; font-size:11px;'>${d.get('vol',0):,.0f}</td>
            </tr>"""
        
        self.wfile.write(f"""<html><head><meta http-equiv='refresh' content='10'><style>
            body {{ background:#050505; color:#eee; font-family:sans-serif; padding:10px; }}
            table {{ border-collapse:collapse; width:100%; background:#0a0a0a; }}
            th {{ background:#111; padding:10px; color:#444; font-size:9px; text-align:left; border-bottom:2px solid #222; }}
            td {{ padding:12px; border-bottom:1px solid #181818; font-size:13px; }}
        </style></head><body>
            <h1 style='color:#00ff88; font-size:20px;'>ULTIMATE WHALE RADAR v3.3</h1>
            <table>
                <tr>
                    <th>SYMBOL</th><th>PRICE</th><th>L/S</th><th>PRESS</th>
                    <th style='color:#00ff88;'>TAKER BUY</th><th style='color:#ff4444;'>TAKER SELL</th>
                    <th style='border-left:2px solid #333;'>LONGS(OI)</th><th>SHORTS(OI)</th><th>EXITS</th><th>LIQ</th><th>OI USD</th><th>24H VOL</th>
                </tr>
                {rows}
            </table>
        </body></html>""".encode())

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
