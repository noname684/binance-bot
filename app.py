import requests, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Настройки чувствительности (через сколько $ реагировать)
LIMITS = {"BTCUSDT": 300000, "ETHUSDT": 150000, "SOLUSDT": 80000}

class QuietServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Bot is live")
    def log_message(self, format, *args): return # Глушим логи сервера

def monitor():
    history_oi = {}
    print("🐳 МОНИТОРИНГ КИТОВ ЗАПУЩЕН...", flush=True)
    while True:
        output = []
        for s in LIMITS.keys():
            try:
                p_data = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={s}").json()
                oi_data = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}").json()
                price, curr_oi = float(p_data['price']), float(oi_data['openInterest']) * float(p_data['price'])
                
                if s in history_oi:
                    diff = curr_oi - history_oi[s]
                    if abs(diff) >= LIMITS[s]:
                        icon = "🟢" if diff > 0 else "🔴"
                        whale = " 🐳🐳🐳" if abs(diff) > LIMITS[s]*3 else ""
                        output.append(f"{icon} {s}: {price}$ | Изм. OI: {diff/1e3:,.1f}k${whale}")
                history_oi[s] = curr_oi
            except: pass
        
        if output:
            print(f"\n--- {time.strftime('%H:%M:%S')} ---", flush=True)
            for line in output: print(line, flush=True)
        time.sleep(20)

if __name__ == "__main__":
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', 10000), QuietServer).serve_forever(), daemon=True).start()
    monitor()
