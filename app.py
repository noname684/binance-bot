import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from datetime import datetime

MONGO_URL = os.getenv("MONGO_URL")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]

try:
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    db = client.market_monitor
    collection = db.daily_stats
    print(">>> DATABASE CONNECTED!", flush=True)
except: pass

def load_data():
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        data = collection.find_one({"date": today})
        if data: return data
    except: pass
    return {"date": today, "assets": {s: {"longs": 0.0, "shorts": 0.0, "liq": 0.0, "price": 0.0, "oi": 0.0, "vol": 0.0, "ratio": 0.0, "fund": 0.0, "action": "WAITING"} for s in SYMBOLS}}

session_data = load_data()

def monitor():
    global session_data
    prev_oi, prev_p = {}, {}
    while True:
        for s in SYMBOLS:
            try:
                # Получаем тикер и фандинг
                r_t = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={s}", timeout=3).json()
                r_f = requests.get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={s}", timeout=3).json()
                r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=3).json()
                r_ls = requests.get(f"https://fapi.binance.com/fapi/v1/data/topLongShortAccountRatio?symbol={s}&period=5m&limit=1", timeout=3).json()
                
                # Имитация проверки ликвидаций через последние сделки (для стабильности)
                r_l = requests.get(f"https://fapi.binance.com/fapi/v1/allForceOrders?symbol={s}&limit=1", timeout=3).json()

                if 'lastPrice' not in r_t: continue
                
                p = float(r_t['lastPrice'])
                oi_usd = float(r_oi['openInterest']) * p
                asset = session_data["assets"][s]
                
                asset["price"], asset["vol"], asset["oi"] = p, float(r_t['quoteVolume']), oi_usd
                asset["fund"] = float(r_f.get('lastFundingRate', 0)) * 100
                if r_ls: asset["ratio"] = float(r_ls[0]['longShortRatio'])
                
                # Если нашли свежую ликвидацию
                if r_l and isinstance(r_l, list):
                    l_val = float(r_l[0].get('origQty', 0)) * p
                    asset['liq'] = l_val
                    if l_val > 50000: asset['action'] = "⚡ LIQUIDATION!"

                if s in prev_oi:
                    d_oi = (float(r_oi['openInterest']) * p) - prev_oi[s]
                    d_p = p - prev_p[s]
                    if d_oi > 1000: # Фильтр шума
                        if d_p > 0: asset['longs'] += d_oi; asset['action'] = "🔥 BUY"
                        else: asset['shorts'] += abs(d_oi); asset['action'] = "💀 SELL"
                
                prev_oi[s], prev_p[s] = oi_usd, p
                collection.update_one({"date": session_data["date"]}, {"$set": session_data}, upsert=True)
            except: pass
        time.sleep(15)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers()
        rows = ""
        for s, d in session_data["assets"].items():
            f_clr = "#ff4444" if d['fund'] > 0.02 else "#00ff88" if d['fund'] < 0 else "#888"
            r_clr = "#ff4444" if d['ratio'] > 1.8 else "#00ff88" if d['ratio'] < 0.9 else "#ccc"
            l_clr = "#ffaa00" if d.get('liq',0) > 0 else "#444"
            rows += f"""
            <tr>
                <td style='font-weight:bold;'>{s}</td>
                <td>{d['price']:,.2f}</td>
                <td style='color:#666;'>${d['vol']:,.0f}</td>
                <td style='color:#00ff88;'>${d['longs']:,.0f}</td>
                <td style='color:#ff4444;'>${d['shorts']:,.0f}</td>
                <td style='color:{l_clr}; font-weight:bold;'>${d.get('liq',0):,.0f}</td>
                <td style='color:{f_clr};'>{d['fund']:.4f}%</td>
                <td style='color:{r_clr};'>{d['ratio']:.2f}</td>
                <td style='background:#1a1a1a; color:{"#00ff88" if "BUY" in d['action'] else "#ff4444" if "SELL" in d['action'] else "#ffaa00"}'>{d['action']}</td>
            </tr>"""
        
        self.wfile.write(f"""
        <html><head><meta http-equiv='refresh' content='15'><style>
            body {{ background: #050505; color: #eee; font-family: monospace; display: flex; flex-direction: column; align-items: center; padding: 15px; }}
            table {{ border-collapse: collapse; width: 100%; max-width: 1250px; background: #0a0a0a; border: 1px solid #222; }}
            th {{ background: #111; padding: 10px; text-align: left; color: #444; font-size: 10px; border-bottom: 1px solid #333; }}
            td {{ padding: 12px; border-bottom: 1px solid #111; font-size: 12px; }}
            h1 {{ color: #00ff88; font-size: 20px; text-shadow: 0 0 15px #00ff8855; }}
        </style></head><body>
            <h1>WHALE RADAR v1.4</h1>
            <table>
                <tr><th>SYMBOL</th><th>PRICE</th><th>24H VOL</th><th>LONGS</th><th>SHORTS</th><th>LAST LIQ</th><th>FUNDING</th><th>L/S RATIO</th><th>SIGNAL</th></tr>
                {rows}
            </table>
        </body></html>""".encode())

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
