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
                # Запросы к API
                r_t = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={s}", timeout=5).json()
                r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                r_dv = requests.get(f"https://fapi.binance.com/futures/data/takerbuybuyvol?symbol={s}&period=5m&limit=1", timeout=5).json()
                
                p = float(r_t['lastPrice'])
                oi_usd = float(r_oi['openInterest']) * p
                
                # Тейкеры и Мейкеры
                if r_dv:
                    t_buy = float(r_dv[0]['buyVol']) * p  # Тейкер купил (значит Мейкер продал)
                    t_sell = (float(r_dv[0]['vol']) * p) - t_buy # Тейкер продал (значит Мейкер купил)
                    m_buy, m_sell = t_sell, t_buy # Прямая зеркальная логика
                else:
                    t_buy = t_sell = m_buy = m_sell = 0

                if s not in session_data["assets"]:
                    session_data["assets"][s] = {"longs":0, "shorts":0, "exit":0, "t_buy":0, "t_sell":0, "m_buy":0, "m_sell":0}
                
                asset = session_data["assets"][s]
                asset.update({
                    "price": p, "oi": oi_usd, "vol": float(r_t['quoteVolume']),
                    "t_buy": t_buy, "t_sell": t_sell, "m_buy": m_buy, "m_sell": m_sell
                })

                if s in prev_oi:
                    d_oi = oi_usd - prev_oi[s]
                    if d_oi > 0:
                        if p >= prev_p[s]: asset['longs'] += d_oi
                        else: asset['shorts'] += d_oi
                    else:
                        asset['exit'] += abs(d_oi)
                
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
            
            # Рендерим строки
            rows += f"""<tr>
                <td style='color:#00ff88;'><b>{s}</b></td>
                <td>{d.get('price',0):,.4f}</td>
                <td style='color:#00ff88;'>${d.get('t_buy',0):,.0f}</td>
                <td style='color:#ff4444;'>${d.get('t_sell',0):,.0f}</td>
                <td style='border-left:2px solid #333; color:#00ff88; opacity:0.7;'>${d.get('m_buy',0):,.0f}</td>
                <td style='color:#ff4444; opacity:0.7;'>${d.get('m_sell',0):,.0f}</td>
                <td style='color:#666; border-left:2px solid #333;'>${d.get('vol',0):,.0f}</td>
                <td style='color:#00d9ff;'>${d.get('oi',0):,.0f}</td>
            </tr>"""
        
        self.wfile.write(f"""<html><head><meta http-equiv='refresh' content='10'><style>
            body {{ background:#050505; color:#eee; font-family:sans-serif; }}
            table {{ border-collapse:collapse; width:100%; background:#0a0a0a; }}
            th {{ background:#111; padding:12px; color:#444; font-size:10px; text-align:left; }}
            td {{ padding:15px; border-bottom:1px solid #181818; font-size:13px; }}
        </style></head><body>
            <h1 style='color:#00ff88; padding:10px;'>TAKER VS MAKER RADAR v3.2</h1>
            <table>
                <tr>
                    <th>SYMBOL</th><th>PRICE</th>
                    <th style='color:#00ff88;'>TAKER BUY (Mkt)</th><th style='color:#ff4444;'>TAKER SELL (Mkt)</th>
                    <th style='color:#00ff88;'>MAKER BUY (Lim)</th><th style='color:#ff4444;'>MAKER SELL (Lim)</th>
                    <th>24H VOL</th><th>OI USD</th>
                </tr>
                {rows}
            </table>
        </body></html>""".encode())

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
