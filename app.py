import requests, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Настройки мониторинга
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
session_data = {
    "longs": 0, "shorts": 0, "start_time": time.time(),
    "history": {} 
}

class UltimateTerminal(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        # РАСЧЕТ ИНДЕКСА СИЛЫ
        total = session_data['longs'] + session_data['shorts'] + 0.1
        power = (session_data['longs'] / total) * 100
        
        # Цвет интерфейса в зависимости от силы
        color = "#ff4444" if power < 40 else "#00ff88" if power > 60 else "#ffd700"
        status_msg = "BEARISH DANGER" if power < 40 else "BULLISH STRENGTH" if power > 60 else "NEUTRAL RANGE"

        html = f"""
        <html><head><meta http-equiv="refresh" content="15">
        <style>
            body {{ background: #050505; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; padding: 20px; }}
            .panel {{ border: 1px solid #222; background: #0f0f0f; padding: 25px; border-radius: 15px; box-shadow: 0 0 40px rgba(0,0,0,0.8); }}
            .index-val {{ font-size: 48px; font-weight: 900; color: {color}; text-shadow: 0 0 20px {color}44; }}
            .bar-bg {{ background: #1a1a1a; height: 10px; border-radius: 5px; margin: 20px 0; border: 1px solid #333; }}
            .bar-fill {{ background: {color}; height: 100%; width: {power}%; box-shadow: 0 0 15px {color}; transition: 1.2s; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 25px; }}
            th {{ text-align: left; font-size: 11px; color: #444; text-transform: uppercase; padding: 10px; border-bottom: 1px solid #222; }}
            td {{ padding: 15px 10px; border-bottom: 1px solid #111; font-size: 15px; }}
            .up {{ color: #00ff88; }} .down {{ color: #ff4444; }}
            .tag {{ font-size: 10px; padding: 4px 8px; border-radius: 4px; font-weight: bold; background: #1a1a1a; border: 1px solid #333; }}
        </style></head><body>
            <div class="panel">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="color:#444; font-size:12px; font-weight:bold;">POWER INDEX</span><br>
                        <span class="index-val">{power:.1f}%</span>
                    </div>
                    <div style="text-align:right;">
                        <span style="color:{color}; font-weight:bold; font-size:18px;">{status_msg}</span><br>
                        <span style="color:#333; font-size:11px;">SERVER: FRANKFURT-DE | ACTIVE</span>
                    </div>
                </div>
                <div class="bar-bg"><div class="bar-fill"></div></div>
                <div style="display:flex; justify-content:space-between; font-size:13px; font-family:monospace;">
                    <span>LONG VOL: <b class="up">${session_data['longs']/1e6:.2f}M</b></span>
                    <span>SHORT VOL: <b class="down">${session_data['shorts']/1e6:.2f}M</b></span>
                </div>
            </div>

            <table>
                <tr><th>Asset</th><th>Live Price</th><th>OI Change (15s)</th><th>Activity</th><th>Phase</th></tr>
        """
        for s in SYMBOLS:
            d = session_data['history'].get(s, {"p":0, "d":0})
            p_color = "up" if d['d'] > 0 else "down"
            phase = "ACCUMULATION" if d['d'] > 0 else "DISTRIBUTION"
            skwiz = "⚡" if abs(d['d']) > 400000 else "" # Индикатор сквиза

            html += f"""
                <tr>
                    <td><b>{s}</b></td>
                    <td class="{p_color}">{d['p']:,.2f}$</td>
                    <td class="{p_color}">{d['d']:+,.0f}$ {skwiz}</td>
                    <td>{ "🐳" if abs(d['d']) > 1000000 else "🐟" }</td>
                    <td><span class="tag" style="color:{color}">{phase}</span></td>
                </tr>
            """
        html += "</table></body></html>"
        self.wfile.write(html.encode('utf-8'))
    def log_message(self, format, *args): return

def monitor():
    global session_data
    prev_oi = {}
    while True:
        for s in SYMBOLS:
            try:
                r_p = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={s}", timeout=5).json()
                r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                p = float(r_p['price'])
                oi = float(r_oi['openInterest']) * p
                
                if s in prev_oi:
                    diff = oi - prev_oi[s]
                    if abs(diff) > 25000:
                        if diff > 0: session_data['longs'] += diff
                        else: session_data['shorts'] += abs(diff)
                        session_data['history'][s] = {"p": p, "d": diff}
                else:
                    session_data['history'][s] = {"p": p, "d": 0}
                prev_oi[s] = oi
            except: pass
        time.sleep(15)

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    HTTPServer(('0.0.0.0', 10000), UltimateTerminal).serve_forever()
