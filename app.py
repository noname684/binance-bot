import requests, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Настройки мониторинга
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
session_data = {
    "longs": 0, "shorts": 0, "exit": 0, 
    "start_time": time.time(),
    "history": {} 
}

def format_currency(value):
    abs_val = abs(value)
    if abs_val >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    elif abs_val >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    elif abs_val >= 1_000:
        return f"{value / 1_000:.0f}k"
    else:
        return f"{value:.0f}"

class UltimateTerminal(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        total_vol = session_data['longs'] + session_data['shorts'] + 0.1
        power = (session_data['longs'] / total_vol) * 100
        color = "#ff4444" if power < 40 else "#00ff88" if power > 60 else "#ffd700"
        
        html = f"""
        <html><head><meta http-equiv="refresh" content="15">
        <style>
            body {{ background: #050505; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; padding: 20px; }}
            .panel {{ border: 1px solid #222; background: #0f0f0f; padding: 25px; border-radius: 15px; }}
            .index-val {{ font-size: 48px; font-weight: 900; color: {color}; }}
            .bar-bg {{ background: #1a1a1a; height: 10px; border-radius: 5px; margin: 20px 0; }}
            .bar-fill {{ background: {color}; height: 100%; width: {power}%; transition: 1s; box-shadow: 0 0 15px {color}; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 25px; }}
            th {{ text-align: left; font-size: 11px; color: #444; text-transform: uppercase; padding: 10px; border-bottom: 2px solid #222; }}
            td {{ padding: 15px 10px; border-bottom: 1px solid #111; font-size: 14px; }}
            .up {{ color: #00ff88; }} .down {{ color: #ff4444; }} .exit-val {{ color: #ffd700; }}
        </style></head><body>
            <div class="panel">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div><span style="color:#444; font-size:12px;">POWER INDEX</span><br><span class="index-val">{power:.1f}%</span></div>
                    <div style="text-align:right;">
                        <span style="color:{color}; font-weight:bold;">SESSION STATS</span><br>
                        <span style="color:#333; font-size:11px;">UPTIME: {int((time.time()-session_data['start_time'])/60)}m</span>
                    </div>
                </div>
                <div class="bar-bg"><div class="bar-fill"></div></div>
                <div style="display:flex; justify-content:space-between; font-size:13px; font-family:monospace;">
                    <span>LONG: <b class="up">${format_currency(session_data['longs'])}</b></span>
                    <span>SHORT: <b class="down">${format_currency(session_data['shorts'])}</b></span>
                    <span>EXIT: <b class="exit-val">${format_currency(session_data['exit'])}</b></span>
                </div>
            </div>

            <table>
                <tr><th>Asset</th><th>Price</th><th>In (Buy/Sell)</th><th>Exit (Out)</th><th>Total OI (Market Cap)</th><th>Whale</th></tr>
        """
        for s in SYMBOLS:
            d = session_data['history'].get(s, {"p":0, "d":0, "total":0, "ex":0})
            p_color = "up" if d['d'] > 0 else "down"
            
            html += f"""
                <tr>
                    <td><b>{s}</b></td>
                    <td class="{p_color}">{d['p']:,.2f}$</td>
                    <td class="{p_color}">{format_currency(d['d'] if d['d'] > 0 else 0)}$ / {format_currency(abs(d['d']) if d['d'] < 0 else 0)}$</td>
                    <td class="exit-val">{format_currency(d['ex'])}$</td>
                    <td><b style="color:#aaa">${format_currency(d['total'])}</b></td>
                    <td>{ "🐳🐳" if abs(d['d']) > 1000000 else "🐳" if abs(d['d']) > 300000 else "🐟" }</td>
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
                    exit_val = 0
                    if abs(diff) > 20000:
                        if diff > 0: 
                            session_data['longs'] += diff
                        else: 
                            session_data['shorts'] += abs(diff)
                            # Считаем выход (условно 20% от шортового импульса или закрытия позиций)
                            exit_val = abs(diff) * 0.4
                            session_data['exit'] += exit_val
                            
                        session_data['history'][s] = {"p": p, "d": diff, "total": oi, "ex": exit_val}
                else:
                    session_data['history'][s] = {"p": p, "d": 0, "total": oi, "ex": 0}
                prev_oi[s] = oi
            except: pass
        time.sleep(15)

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    HTTPServer(('0.0.0.0', 10000), UltimateTerminal).serve_forever()
