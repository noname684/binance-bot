import requests, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Настройки
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
session_data = {
    "start_time": time.time(),
    "assets": {s: {"longs": 0, "shorts": 0, "exit": 0, "price": 0, "oi": 0, "last_diff": 0} for s in SYMBOLS}
}

def format_currency(value):
    abs_val = abs(value)
    if abs_val >= 1_000_000_000: return f"{value / 1_000_000_000:.2f}B"
    elif abs_val >= 1_000_000: return f"{value / 1_000_000:.2f}M"
    elif abs_val >= 1_000: return f"{value / 1_000:.0f}k"
    return f"{value:.0f}"

class AssetTerminal(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        # Общая сила рынка для заголовка
        t_l = sum(a['longs'] for a in session_data['assets'].values())
        t_s = sum(a['shorts'] for a in session_data['assets'].values())
        power = (t_l / (t_l + t_s + 0.1)) * 100
        color = "#ff4444" if power < 45 else "#00ff88" if power > 55 else "#ffd700"

        html = f"""
        <html><head><meta http-equiv="refresh" content="15">
        <style>
            body {{ background: #050505; color: #e0e0e0; font-family: 'Consolas', monospace; padding: 15px; }}
            .header {{ background: #111; padding: 15px; border-radius: 10px; border-left: 5px solid {color}; margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; background: #0a0a0a; }}
            th {{ text-align: left; font-size: 10px; color: #555; padding: 10px; border-bottom: 2px solid #222; }}
            td {{ padding: 12px 10px; border-bottom: 1px solid #151515; font-size: 13px; }}
            .up {{ color: #00ff88; }} .down {{ color: #ff4444; }} .exit {{ color: #ffd700; }}
            .symbol {{ font-size: 16px; font-weight: bold; color: #fff; }}
            .mini-label {{ font-size: 9px; color: #444; display: block; }}
        </style></head><body>
            <div class="header">
                <span style="font-size: 20px; font-weight: 900; color: {color};">MARKET POWER: {power:.1f}%</span>
                <span style="float: right; color: #333;">RUNTIME: {int((time.time()-session_data['start_time'])/60)}m</span>
            </div>
            <table>
                <tr>
                    <th>ASSET / PRICE</th>
                    <th>LAST CHANGE (15s)</th>
                    <th>SESSION LONGS</th>
                    <th>SESSION SHORTS</th>
                    <th>SESSION EXIT</th>
                    <th>TOTAL OI</th>
                </tr>
        """
        for s in SYMBOLS:
            a = session_data['assets'][s]
            diff_color = "up" if a['last_diff'] > 0 else "down"
            
            html += f"""
                <tr>
                    <td><span class="symbol">{s}</span><br><span style="color:#888">{a['price']:,.2f}$</span></td>
                    <td class="{diff_color}"><b>{format_currency(a['last_diff'])}$</b></td>
                    <td class="up">{format_currency(a['longs'])}$</td>
                    <td class="down">{format_currency(a['shorts'])}$</td>
                    <td class="exit">{format_currency(a['exit'])}$</td>
                    <td><b style="color:#aaa">${format_currency(a['oi'])}</b></td>
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
                    session_data['assets'][s]['price'] = p
                    session_data['assets'][s]['oi'] = oi
                    session_data['assets'][s]['last_diff'] = diff
                    
                    if abs(diff) > 20000:
                        if diff > 0:
                            session_data['assets'][s]['longs'] += diff
                        else:
                            session_data['assets'][s]['shorts'] += abs(diff)
                            session_data['assets'][s]['exit'] += abs(diff) * 0.4
                else:
                    session_data['assets'][s]['price'] = p
                    session_data['assets'][s]['oi'] = oi
                prev_oi[s] = oi
            except: pass
        time.sleep(15)

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    HTTPServer(('0.0.0.0', 10000), AssetTerminal).serve_forever()
