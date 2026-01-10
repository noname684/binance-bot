import requests, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Настройки
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
session_stats = {"longs": 0, "shorts": 0, "exit": 0}
current_assets = {}

class PowerTerminal(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        # РАСЧЕТ ИНДЕКСА СИЛЫ
        total_vol = session_stats['longs'] + session_stats['shorts'] + 1
        power_index = (session_stats['longs'] / total_vol) * 100
        
        # Определение цвета и текста индекса
        if power_index > 60: 
            status_text, status_color = "BULLISH STRENGTH", "#00ff88"
        elif power_index < 40: 
            status_text, status_color = "BEARISH PRESSURE", "#ff4444"
        else: 
            status_text, status_color = "NEUTRAL MARKET", "#ffd700"

        html = f"""
        <html><head><meta http-equiv="refresh" content="15">
        <style>
            body {{ background: #0a0a0a; color: #d4d4d4; font-family: 'Consolas', monospace; padding: 20px; }}
            .power-box {{ border: 2px solid {status_color}; padding: 15px; border-radius: 10px; margin-bottom: 20px; background: rgba(255,255,255,0.03); }}
            .index-bar-bg {{ background: #333; height: 10px; border-radius: 5px; margin-top: 10px; overflow: hidden; }}
            .index-bar-fill {{ background: {status_color}; height: 100%; width: {power_index}%; transition: 0.5s; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th {{ text-align: left; color: #666; padding: 10px; border-bottom: 1px solid #333; font-size: 12px; }}
            td {{ padding: 12px; border-bottom: 1px solid #1a1a1a; }}
            .green {{ color: #00ff88; }} .red {{ color: #ff4444; }} .yellow {{ color: #ffd700; }}
            .glitch {{ font-weight: bold; text-shadow: 0 0 5px {status_color}; }}
        </style></head><body>
            <div class="power-box">
                <div style="display: flex; justify-content: space-between;">
                    <span>MARKET POWER INDEX: <b class="glitch" style="color: {status_color}">{power_index:.1f}%</b></span>
                    <span style="color: {status_color}">{status_text}</span>
                </div>
                <div class="index-bar-bg"><div class="index-bar-fill"></div></div>
                <div style="margin-top: 10px; font-size: 12px; color: #888;">
                    SESSION LONGS: <span class="green">${session_stats['longs']/1e6:.1f}M</span> | 
                    SHORTS: <span class="red">${session_stats['shorts']/1e6:.1f}M</span> | 
                    EXITS: <span class="yellow">${session_stats['exit']/1e6:.1f}M</span>
                </div>
            </div>

            <table>
                <tr><th>ASSET</th><th>LIVE PRICE</th><th>OI CHANGE (15s)</th><th>WHALE ACTIVITY</th><th>TOTAL OI</th></tr>
        """
        
        for s in SYMBOLS:
            d = current_assets.get(s, {"price":0, "diff":0, "total":0})
            color = "green" if d['diff'] > 0 else "red" if d['diff'] < 0 else ""
            whale = "🐳🐳🐳" if abs(d['diff']) > 1000000 else "🐳" if abs(d['diff']) > 300000 else ""
            
            html += f"""
                <tr>
                    <td><b>{s}</b></td>
                    <td class="{color}">{d['price']:,.2f}$</td>
                    <td class="{color}">{d['diff']:+,.0f}$</td>
                    <td class="{color}">{whale}</td>
                    <td>${d['total']/1e6:.1f}M</td>
                </tr>
            """
        
        html += "</table><div style='margin-top:20px; font-size:10px; color:#444;'>STATION: FRANKFURT | DATA: BINANCE FUTURES</div></body></html>"
        self.wfile.write(html.encode('utf-8'))
    def log_message(self, format, *args): return

def monitor():
    global current_assets, session_stats
    history_oi = {}
    while True:
        for s in SYMBOLS:
            try:
                p_res = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={s}", timeout=5).json()
                oi_res = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                price = float(p_res['price'])
                oi_usd = float(oi_res['openInterest']) * price
                
                if s in history_oi:
                    diff = oi_usd - history_oi[s]
                    if abs(diff) > 20000:
                        if diff > 0: session_stats['longs'] += diff
                        else: session_stats['shorts'] += abs(diff); session_stats['exit'] += abs(diff)*0.2
                        current_assets[s] = {"price": price, "diff": diff, "total": oi_usd}
                else:
                    current_assets[s] = {"price": price, "diff": 0, "total": oi_usd}
                history_oi[s] = oi_usd
            except: pass
        time.sleep(15)

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    HTTPServer(('0.0.0.0', 10000), PowerTerminal).serve_forever()
