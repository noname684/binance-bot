import requests, time, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "1000PEPEUSDT", "SUIUSDT", "XRPUSDT", "1000WHYUSDT"]
# Инициализация с полным набором ключей сразу, чтобы избежать KeyError
data_store = {s: {"p":0, "ls":0, "tb":0, "ts":0, "mb":0, "ms":0, "l":0, "sh":0, "ex":0, "liq":0, "oi":0, "v":0} for s in SYMBOLS}

def monitor():
    prev = {}
    while True:
        for s in SYMBOLS:
            try:
                t = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={s}", timeout=5).json()
                o = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                ls = requests.get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={s}&period=5m&limit=1", timeout=5).json()
                dv = requests.get(f"https://fapi.binance.com/futures/data/takerbuybuyvol?symbol={s}&period=5m&limit=1", timeout=5).json()
                
                p = float(t['lastPrice'])
                oi_usd = float(o['openInterest']) * p
                tb = float(dv[0]['buyVol']) * p if dv else 0
                ts = (float(dv[0]['vol']) * p) - tb if dv else 0
                
                # Обновляем данные в хранилище
                data_store[s].update({
                    "p": p, "ls": float(ls[0]['longShortRatio']) if ls else 0, 
                    "tb": tb, "ts": ts, "mb": ts, "ms": tb,
                    "oi": oi_usd, "v": float(t['quoteVolume'])
                })

                if s in prev:
                    d_oi = oi_usd - prev[s]['oi']
                    d_p = p - prev[s]['p']
                    if d_oi > 0:
                        if d_p >= 0: data_store[s]['l'] += d_oi
                        else: data_store[s]['sh'] += d_oi
                    else:
                        data_store[s]['ex'] += abs(d_oi)
                        if abs(d_p/p) > 0.0015: data_store[s]['liq'] += abs(d_oi)
                
                prev[s] = {"oi": oi_usd, "p": p}
            except: pass
        time.sleep(10)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers()
        rows = ""
        for s in SYMBOLS:
            d = data_store[s]
            tb, ts = d.get('tb', 0), d.get('ts', 0)
            total = tb + ts
            pres = ((tb - ts) / total * 100) if total > 0 else 0
            pres_clr = "#00ff88" if pres > 0 else "#ff4444"

            rows += f"""<tr>
                <td style='color:#00ff88; font-size:16px;'><b>{s}</b></td>
                <td style='font-family:monospace;'>{d.get('p',0):,.4f}</td>
                <td style='color:#aaa;'>{d.get('ls',0):,.2f}</td>
                <td style='color:{pres_clr}; font-weight:bold;'>{pres:+.1f}%</td>
                <td style='color:#00ff88;'>${tb:,.0f}</td>
                <td style='color:#ff4444;'>${ts:,.0f}</td>
                <td style='color:#00ff88; opacity:0.5;'>${d.get('mb',0):,.0f}</td>
                <td style='color:#ff4444; opacity:0.5;'>${d.get('ms',0):,.0f}</td>
                <td style='border-left:2px solid #333; color:#00ff88;'>${d.get('l',0):,.0f}</td>
                <td style='color:#ff4444;'>${d.get('sh',0):,.0f}</td>
                <td style='color:#ffaa00;'>${d.get('ex',0):,.0f}</td>
                <td style='color:#ff0055;'>${d.get('liq',0):,.0f}</td>
                <td style='color:#00d9ff;'>${d.get('oi',0):,.0f}</td>
                <td style='color:#444; font-size:11px;'>${d.get('v',0):,.0f}</td>
            </tr>"""
        
        self.wfile.write(f"""<html><head><meta http-equiv='refresh' content='10'><style>
            body{{background:#050505; color:#eee; font-family:sans-serif; padding:20px;}}
            table{{width:100%; border-collapse:collapse; background:#0a0a0a;}}
            th{{background:#111; padding:12px; color:#444; font-size:10px; text-align:left; text-transform:uppercase;}}
            td{{padding:12px; border-bottom:1px solid #181818; font-size:13px;}}
        </style></head><body>
            <h1 style='color:#00ff88;'>WHALE RADAR PRO v3.5.1</h1>
            <table>
                <tr>
                    <th>Symbol</th><th>Price</th><th>L/S</th><th>Press</th>
                    <th style='color:#00ff88;'>Taker Buy</th><th style='color:#ff4444;'>Taker Sell</th>
                    <th style='color:#008844;'>Maker Buy</th><th style='color:#880022;'>Maker Sell</th>
                    <th style='border-left:2px solid #333;'>Longs(OI)</th><th>Shorts(OI)</th><th>Exits</th><th>Liq</th><th>OI USD</th><th>24h Vol</th>
                </tr>
                {rows}
            </table>
        </body></html>""".encode())

threading.Thread(target=monitor, daemon=True).start()
HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), H).serve_forever()
