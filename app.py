import requests, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Настройки мониторинга
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
session_stats = {"longs": 0, "shorts": 0, "exit": 0, "start_time": time.time()}
current_assets = {}

class UltimateTerminal(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        # РАСЧЕТ ИНДЕКСА
        total_vol = session_stats['longs'] + session_stats['shorts'] + 0.001
        power_index = (session_stats['longs'] / total_vol) * 100
        
        # Цветовая схема на основе индекса
        if power_index > 65: status, color = "STRONG BULLISH", "#00ff88"
        elif power_index > 50: status, color = "MILD BULLISH", "#a2ff00"
        elif power_index > 35: status, color = "NEUTRAL", "#ffd700"
        else: status, color = "BEARISH DANGER", "#ff4444"

        uptime = int((time.time() - session_stats['start_time']) / 60)

        html = f"""
        <html><head><meta http-equiv="refresh" content="15">
        <style>
            body {{ background: #050505; color: #e0e0e0; font-family: 'Segoe UI', monospace; padding: 20px; }}
            .panel {{ border: 1px solid #333; background: #111; padding: 20px; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
            .index-val {{ font-size: 32px; font-weight: 900; color: {color}; }}
            .bar-container {{ background: #222; height: 8px; border-radius: 4px; margin: 15px 0; }}
            .bar-fill {{ background: {color}; height: 100%; width: {power_index}%; box-shadow: 0 0 15px {color}; border-radius: 4px; transition: 1s; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th {{ text-align: left; font-size: 11px; color: #555; text-transform: uppercase; padding-bottom: 10px; }}
            td {{ padding: 15px 10px; border-bottom: 1px solid #1a1a1a; font-size: 14px; }}
            .trend-up {{ color: #00ff88; }} .trend-down {{ color: #ff4444; }}
            .whale-tag {{ background: rgba(255,215,0,0.1); color: #ffd700; padding: 2px 6px; border-radius: 4px; font-size: 10px; }}
        </style>
        </head><body>
            <div class="panel">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="color:#666; font-size:12px;">MARKET POWER SENSE</span><br>
                        <span class="index-val">{power_index:.1f}%</span>
                    </div>
                    <div style="text-align:right;">
                        <span style="color:{color}; font-weight:bold; letter-spacing:1px;">{status}</span><br>
                        <span style="color:#444; font-size:11px;">UPTIME: {uptime} MIN | FRANKFURT NODE</span>
                    </div>
                </div>
                <div class="bar-container"><div class="bar-fill"></div></div>
                <div style="display:flex; justify-content:space-between; font-size:12px;">
                    <span>LONG: <b class="trend-up">${session_stats['longs']/1e6:.2f}M</b></span>
                    <span>SHORT: <b class="trend-down">${session_stats['shorts']/1e6:.2f}M</b></span>
                    <span>EXITS: <b style="color:#ffd700;">${session_stats['exit']/1e6:.2f}M</b></span>
                </div>
            </div>

            <table>
                <tr><th>Asset</th><th>Price</th><th>OI Change</th><th>Signal</th><th>Market Cap (OI)</th></tr>
        """
        for s in SYMBOLS:
            d = current_assets.get(s, {"price":0, "diff":0, "total":0})
            cls = "trend-up" if d['diff'] > 0 else "trend-down"
            sig = "BUY" if d['diff'] > 0 else "SELL"
            whale = '<span class="whale-tag">WHALE 🐳</span>' if abs(d['diff']) > 500000 else ""
            
            html += f"""
                <tr>
                    <td><b>{s}</b></td>
                    <td class="{cls}">{d['price']:,.2f}$</td>
                    <td class="{cls}">{d['diff']:+,.0f}$</td>
                    <td><b class="{cls}">{sig}</b> {whale}</td>
                    <td style="color:#666;">${d['total']/1e6:.1f}M</td>
                </tr>
            """
        html += "</table></body></html>"
        self.wfile.write(html.encode('utf-8'))
    def log_message(self, format, *args): return

def monitor():
    global current_assets, session_stats
    hist = {}
    while True:
        for s in SYMBOLS:
            try:
                p = float(requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={s}").json()['price'])
                oi = float(requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}").json()['openInterest']) * p
                if s in hist:
                    diff = oi - hist[s]
                    if abs(diff) > 20000:
                        if diff > 0: session_stats['longs'] += diff
                        else: session_stats['shorts'] += abs(diff); session_stats['exit'] += abs(diff)*0.1
                        current_assets[s] = {"price": p, "diff": diff, "total": oi}
                else: current_assets[s] = {"price": p, "diff": 0, "total": oi}
                hist[s] = oi
            except: pass
        time.sleep(15)

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    HTTPServer(('0.0.0.0', 10000), UltimateTerminal).serve_forever()
