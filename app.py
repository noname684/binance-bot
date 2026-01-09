import requests, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Настройки мониторинга
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
data_log = [] # Тут храним последние 20 событий для таблицы

class WebDashboard(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        # Генерируем HTML-страницу (как мини-сайт)
        html = """
        <html><head><meta http-equiv="refresh" content="30"><style>
            body { font-family: sans-serif; background: #121212; color: white; padding: 20px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 12px; border: 1px solid #333; text-align: left; }
            th { background: #1e1e1e; }
            .green { color: #00ff88; font-weight: bold; }
            .red { color: #ff4444; font-weight: bold; }
            .whale { font-size: 20px; }
        </style></head><body>
            <h2>🐳 Whale Monitor Dashboard</h2>
            <p>Обновляется каждые 30 секунд. Регион: Frankfurt.</p>
            <table>
                <tr><th>Время</th><th>Монета</th><th>Цена</th><th>Изм. OI ($)</th><th>Статус</th></tr>
        """
        for entry in reversed(data_log[-20:]): # Показываем последние 20 записей
            style = "green" if entry['diff'] > 0 else "red"
            whale = "🐳" if abs(entry['diff']) > 500000 else ""
            html += f"<tr><td>{entry['time']}</td><td>{entry['symbol']}</td><td>{entry['price']}$</td>"
            html += f"<td class='{style}'>{entry['diff']:,.0f}$</td><td>{entry['status']} {whale}</td></tr>"
        
        html += "</table></body></html>"
        self.wfile.write(html.encode())

    def log_message(self, format, *args): return

def monitor():
    global data_log
    history_oi = {}
    while True:
        for s in SYMBOLS:
            try:
                p_res = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={s}", timeout=5).json()
                oi_res = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                price, oi_usd = float(p_res['price']), float(oi_res['openInterest']) * float(p_res['price'])
                
                if s in history_oi:
                    diff = oi_usd - history_oi[s]
                    if abs(diff) > 50000: # Порог шума
                        status = "ВЛИТО" if diff > 0 else "ВЫХОД"
                        data_log.append({
                            "time": time.strftime("%H:%M:%S"), "symbol": s, 
                            "price": price, "diff": diff, "status": status
                        })
                history_oi[s] = oi_usd
            except: pass
        time.sleep(30)

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    HTTPServer(('0.0.0.0', 10000), WebDashboard).serve_forever()
