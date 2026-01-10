import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

MONGO_URL = os.getenv("MONGO_URL")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "1000WHYUSDT"]

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
                # 1. Запросы к API
                r_t = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={s}", timeout=5).json()
                r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                r_ls = requests.get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={s}&period=5m&limit=1", timeout=5).json()
                
                p = float(r_t['lastPrice'])
                vol_24h = float(r_t['quoteVolume'])
                oi_usd = float(r_oi['openInterest']) * p
                ls_ratio = float(r_ls[0]['longShortRatio']) if r_ls else 0
                
                if s not in session_data["assets"]:
                    session_data["assets"][s] = {"longs":0.0, "shorts":0.0, "exit":0.0, "liq":0.0, "price":p, "ls":ls_ratio, "oi":oi_usd}
                
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
                        # Если цена сильно дернулась при падении OI - считаем это ликвидацией (упрощенно)
                        if abs(d_p/p) > 0.001: asset['liq'] += abs(d_oi)
                
                prev_oi[s], prev_p[s] = oi_usd, p
            except: pass
        
        collection.update_one({"date": session_data["date"]}, {"$set": session_data}, upsert=True)
        time.sleep(12)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers()
        rows = ""
        for s in SYMBOLS:
            d = session_data["assets"].get(s, {})
            ls = d.get('ls', 0)
            ls_clr = "#ff4444" if ls > 1.5 else "#00ff88" if ls < 0.8 else "#aaa"
            price = d.get('price', 0)
            p_format = f"{price:,.8f}" if price < 0.01 else f"{price:,.4f}" if price < 100 else f"{price:,.2f}"

            rows += f"""<tr>
                <td class='sym'><b>{s}</b></td>
                <td class='num'>{p_format}</td>
                <td class='num' style='color:{ls_clr}; font-weight:bold;'>{ls:.2f}</td>
                <td class='num' style='color:#00ff88;'>${d.get('longs',0):,.0f}</td>
                <td class='num' style='color:#ff4444;'>${d.get('shorts',0):,.0f}</td>
                <td class='num' style='color:#ffaa00;'>${d.get('exit',0):,.0f}</td>
                <td class='num' style='color:#ff0055; background:rgba(255,0,85,0.1); font-weight:bold;'>${d.get('liq',0):,.0f}</td>
                <td class='num' style='color:#00d9ff;'>${d.get('oi',0):,.0f}</td>
            </tr>"""
        
        self.wfile.write(f"""<html><head><meta http-equiv='refresh' content='12'><style>
            body {{ background:#050505; color:#eee; font-family:sans-serif; padding:20px; }}
            table {{ border-collapse:collapse; width:100%; max-width:1400px; background:#0a0a0a; border:2px solid #222; }}
            th {{ background:#151515; padding:15px; text-align:left; color:#666; font-size:12px; border-bottom:2px solid #333; }}
            td {{ padding:18px; border-bottom:1px solid #111; font-size:16px; min-width:120px; }}
            .sym {{ color:#00ff88; font-size:18px; }}
            .num {{ font-family:'Courier New', monospace; text-align:right; }}
            h1 {{ color:#00ff88; letter-spacing:2px; margin-bottom:30px; }}
        </style></head><body>
            <h1>WHALE TERMINAL v2.5</h1>
            <table>
                <tr>
                    <th>SYMBOL</th><th>PRICE</th><th>L/S RATIO</th><th>LONGS (IN)</th><th>SHORTS (IN)</th><th>EXITS (OUT)</th><th>LIQUIDATIONS</th><th>OPEN INTEREST</th>
                </tr>
                {rows}
            </table>
        </body></html>""".encode())

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
