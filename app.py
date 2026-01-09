import requests
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- Секция для Render (чтобы не банили) ---
class SimpleServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Monitor is Active")

def run_web_server():
    # Порт 10000 — стандарт для Render
    server = HTTPServer(('0.0.0.0', 10000), SimpleServer)
    server.serve_forever()

# --- Секция Мониторинга Binance ---
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
history_oi = {}

def get_data(symbol):
    try:
        # Прямые запросы к Binance из Германии
        url = f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}"
        p_url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
        
        price = float(requests.get(p_url, timeout=10).json()['price'])
        oi = float(requests.get(url, timeout=10).json()['openInterest'])
        return oi * price, price
    except:
        return None, None

def monitor():
    print("🚀 МОНИТОРИНГ ЗАПУЩЕН ВО ФРАНКФУРТЕ", flush=True)
    while True:
        print(f"\n--- Проверка {time.strftime('%H:%M:%S')} ---", flush=True)
        for s in SYMBOLS:
            curr_oi, price = get_data(s)
            if curr_oi is not None:
                if s in history_oi:
                    diff = curr_oi - history_oi[s]
                    status = ""
                    if diff > 50000: status = "🟢 ВЛИТО"
                    elif diff < -50000: status = "🔴 ВЫХОД"
                    
                    print(f"{s}: {price}$ | Изм. OI: {diff:,.0f}$ {status}", flush=True)
                else:
                    print(f"{s}: {price}$ | База создана", flush=True)
                history_oi[s] = curr_oi
        time.sleep(30)

if __name__ == "__main__":
    # Запускаем веб-заглушку в фоновом потоке
    threading.Thread(target=run_web_server, daemon=True).start()
    # Запускаем основной цикл в главном потоке
    monitor()
