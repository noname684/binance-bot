import requests, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Настройки
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
session_data = {
    "start_time": time.time(),
    "assets": {s: {"longs": 0.1, "shorts": 0.1, "exit": 0, "price": 0, "oi": 0, "last_diff": 0} for s in SYMBOLS}
}

def format_currency(value):
    abs_val = abs(value)
    if abs_val >= 1_000_000_000: return f"{value / 1_000_000_000:.2f}B"
    elif abs_val >= 1_000_000: return f"{value / 1_000_000:.2f}M"
    elif abs_val >= 1_000: return f"{value / 1_000:.0f}k"
    return f"{value:.0f}"

class DeepMetricsTerminal(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        t_l = sum(a['longs'] for a in session_data['assets'].values())
        t_s = sum(a['shorts'] for a in session_data['assets'].values())
        power = (t_l / (t_l + t_s + 0.1)) * 100
        color = "#ff4444" if power < 45 else "#00ff88" if power > 55 else "#ffd700"

        html = f"""
        <html><head><meta http-equiv="refresh" content="15">
        <style>
            body {{ background: #050505; color: #e0e0e0; font-family: 'Inter', sans-serif; padding: 20px; }}
            .header {{ background: #111; padding: 20px; border-radius: 12px; margin-bottom: 25px; border-bottom: 3px solid {color}; }}
            table {{ width: 100%; border-collapse: collapse; border-radius: 8px; overflow: hidden; }}
            th {{ text-align: left; font-size: 10px; color: #555; padding: 12px; background: #0c0c0c; }}
            td {{ padding: 15px 12px; border-bottom: 1px solid #151515; font-size: 14px; background: #0a0a0a; }}
            .up {{ color: #00ff88; }} .down {{ color: #ff4444; }} .exit {{ color: #ffd700; }}
            .trend-bar {{ height: 4px; background: #222; border-radius: 2px; margin-top: 8px; width: 100px; }}
            .trend-fill {{ height: 100%; border-radius: 2px; }}
        </style></head><body>
            <div class="header">
                <span style="font-size: 28px; font-weight: 900; color: {color};">GLOBAL SENSE: {power:.1f}%</span>
                <span style="float: right; color: #444;">ACTIVE SINCE: {int((time.time()-session_data['start_time'])/60)}m</span>
            </div>
            <table>
                <tr>
                    <th>ASSET / PRICE</th>
                    <th>STRENGTH / TREND</th>
                    <th>SESSION LONG</th>
                    <th>SESSION SHORT</th>
                    <th>SESSION EXIT</th>
                    <th>TOTAL OI</th>
                </tr>
        """
        for s in SYMBOLS:
            a = session_data['assets'][s]
            # Расчет силы тренда для каждой монеты
            asset_total = a['longs'] + a['shorts']
            asset_power = (a['longs'] / asset_total) * 100
            a_color = "#00ff88" if asset_power > 50 else "#ff4444"
            
            html += f"""
                <tr>
                    <td><b style="font-size:16px;">{s}</b><br><span style="color:#666;">{a['price']:,.2f}$</span></td>
                    <td>
                        <b style="color:{a_color}">{asset_power:.1f}%</b>
                        <div class="trend-bar"><div class="trend-fill" style="width:{asset_power}%; background:{a_color};"></div></div>
                    </td>
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
    HTTPServer(('0.0.0.0', 10000), DeepMetricsTerminal).serve_forever()
