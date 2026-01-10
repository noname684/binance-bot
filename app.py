import requests, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Настройки мониторинга
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
session_data = {
    "longs": 0, "shorts": 0, "start_time": time.time(),
    "history": {} 
}

# Идеальное форматирование (B, M, k)
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
        
        total = session_data['longs'] + session_data['shorts'] + 0.1
        power = (session_data['longs'] / total) * 100
        color = "#ff4444" if power < 40 else "#00ff88" if power > 60 else "#ffd700"
        
        html = f"""
        <html><head><meta http-equiv="refresh" content="15">
        <style>
            body {{ background: #050505; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; padding: 20px; }}
            .panel {{ border: 1px solid #222; background: #0f0f0f; padding: 25px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.7); }}
            .index-val {{ font-size: 48px; font-weight: 900; color: {color}; text-shadow: 0 0 20px {color}44; }}
            .bar-bg {{ background: #1a1a1a; height: 12px; border-radius: 6px; margin: 20px 0; border: 1px solid #333; }}
            .bar-fill {{ background: {color}; height: 100%; width: {power}%; transition: 1.2s ease-in-out; box-shadow: 0 0 15px {color}; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 25px; }}
            th {{ text-align: left; font-size: 11px; color: #555; text-transform: uppercase; padding: 12px; border-bottom: 2px solid #222; }}
            td {{ padding: 15px 12px; border-bottom: 1px solid #111; font-size: 15px; }}
            .up {{ color: #00ff88; font-weight: bold; }} .down {{ color: #ff4444; font-weight: bold; }}
            .tag {{ font-size: 10px; padding: 4px 8px; border-radius: 4px; font-weight: bold; background: #1a1a1a; border: 1px solid #333; }}
            .whale-anim {{ font-size: 20px; filter: drop-shadow(0 0 5px rgba(255,255,255,0.3)); }}
        </style></head><body>
            <div class="panel">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="color:#666; font-size:12px; font-weight:bold; letter-spacing:1px;">MARKET POWER SENSE</span><br>
                        <span class="index-val">{power:.1f}%</span>
                    </div>
                    <div style="text-align:right;">
                        <span style="color:{color}; font-weight:bold; font-size:18px;">SESSION VOLUME</span><br>
                        <span style="color:#444; font-size:11px;">NODE: FRANKFURT | UP: {int((time.time()-session_data['start_time'])/60)}m</span>
                    </div>
                </div>
                <div class="bar-bg"><div class="bar-fill"></div></div>
                <div style="display:flex; justify-content:space-between; font-size:13px; font-family:monospace; background:#000; padding:10px; border-radius:5px;">
                    <span>LONG: <b class="up">${format_currency(session_data['longs'])}</b></span>
                    <span>SHORT: <b class="down">${format_currency(session_data['shorts'])}</b></span>
                </div>
            </div>

            <table>
                <tr><th>Asset</th><th>Live Price</th><th>OI Change (15s)</th><th>Whale Activity</th><th>Total OI (B/M)</th><th>Market Phase</th></tr>
        """
        for s in SYMBOLS:
            d = session_data['history'].get(s, {"p":0, "d":0, "total":0})
            p_color = "up" if d['d'] > 0 else "down"
            phase = "ACCUMULATION" if d['d'] > 0 else "DISTRIBUTION"
            skwiz = "⚡" if abs(d['d']) > 500000 else ""

            # Логика значков китов
            whale_icon = "🐟"
            if abs(d['d']) > 1_500_000: whale_icon = "🐳🐳🐳"
            elif abs(d['d']) > 800_000: whale_icon = "🐳🐳"
            elif abs(d['d']) > 300_000: whale_icon = "🐳"

            html += f"""
                <tr>
                    <td><b style="color:#fff">{s}</b></td>
                    <td class="{p_color}">{d['p']:,.2f}$</td>
                    <td class="{p_color}">{format_currency(d['d'])}$ {skwiz}</td>
                    <td class="whale-anim">{whale_icon}</td>
                    <td><b style="color:#aaa">${format_currency(d['total'])}</b></td>
                    <td><span class="tag" style="color:{color}">{phase}</span></td>
                </tr>
            """
        html += "</table><div style='margin-top:20px; font-size:11px; color:#333;'>* Сортировка по волатильности активна. Обновление 15с.</div></body></html>"
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
                        session_data['history'][s] = {"p": p, "d": diff, "total": oi}
                else:
                    session_data['history'][s] = {"p": p, "d": 0, "total": oi}
                prev_oi[s] = oi
            except: pass
        time.sleep(15)

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    HTTPServer(('0.0.0.0', 10000), UltimateTerminal).serve_forever()
