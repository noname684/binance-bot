import requests, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Настройки
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
# Порог срабатывания: записывать в ленту только если движение > $100,000
SENSITIVITY = 100000 
event_history = [] # Лента событий

class ColabStyleDashboard(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        html = """
        <html><head>
            <meta http-equiv="refresh" content="20">
            <style>
                body { font-family: monospace; background: #1c1c1c; color: #d4d4d4; padding: 20px; }
                .line { border-left: 3px solid #333; padding-left: 15px; margin-bottom: 8px; }
                .time { color: #888; font-size: 12px; }
                .symbol { color: #569cd6; font-weight: bold; margin-left: 10px; }
                .price { color: #ce9178; margin-left: 10px; }
                .diff { font-weight: bold; margin-left: 10px; }
                .green { color: #4ec9b0; }
                .red { color: #f44747; }
                .whale { font-size: 18px; margin-left: 5px; }
                h2 { color: #6a9955; font-size: 18px; border-bottom: 1px solid #333; padding-bottom: 10px; }
            </style>
        </head><body>
            <h2>[Binance_Live_Feed_Terminal]</h2>
        """
        
        if not event_history:
            html += "<p>Сканирование рынка... Ждите крупных сделок...</p>"
        
        # Выводим историю: новые сверху
        for ev in reversed(event_history[-40:]):
            color = "green" if ev['diff'] > 0 else "red"
            sign = "+" if ev['diff'] > 0 else ""
            whale = " 🐳" if abs(ev['diff']) > 1000000 else ""
            
            html += f"""
            <div class="line">
                <span class="time">[{ev['time']}]</span>
                <span class="symbol">{ev['symbol']}</span>
                <span class="price">{ev['price']}$</span>
                <span class="diff {color}">{sign}{ev['diff']:,.0f}$</span>
                <span>{ev['status']}</span>{whale}
            </div>
            """
        
        html += "</body></html>"
        self.wfile.write(html.encode('utf-8'))
    def log_message(self, format, *args): return

def monitor():
    global event_history
    history_oi = {}
    while True:
        for s in SYMBOLS:
            try:
                p_data = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={s}", timeout=5).json()
                oi_data = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                price = float(p_data['price'])
                curr_oi_usd = float(oi_data['openInterest']) * price
                
                if s in history_oi:
                    diff = curr_oi_usd - history_oi[s]
                    # РЕГИСТРИРУЕМ ТОЛЬКО ВАЖНЫЕ ДВИЖЕНИЯ
                    if abs(diff) > SENSITIVITY:
                        event_history.append({
                            "time": time.strftime("%H:%M:%S"),
                            "symbol": s, "price": price, "diff": diff,
                            "status": "BUY_VOL" if diff > 0 else "SELL_VOL"
                        })
                history_oi[s] = curr_oi_usd
            except: pass
        time.sleep(20)

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    HTTPServer(('0.0.0.0', 10000), ColabStyleDashboard).serve_forever()
