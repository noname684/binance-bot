import requests, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- ПРЕДЕЛЫ ДЛЯ УВЕДОМЛЕНИЙ (в долларах) ---
# Бот напишет только если движение больше этой суммы:
LIMITS = {
    "BTCUSDT": 1000000,  # 1 миллион $
    "ETHUSDT": 500000,   # 500 тысяч $
    "SOLUSDT": 250000    # 250 тысяч $
}

class QuietServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Whale Monitor is Active")
    def log_message(self, format, *args): return # Убирает мусор из логов

def get_data(symbol):
    try:
        p_url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
        oi_url = f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}"
        price = float(requests.get(p_url, timeout=5).json()['price'])
        oi_usd = float(requests.get(oi_url, timeout=5).json()['openInterest']) * price
        return oi_usd, price
    except: return None, None

def monitor():
    history_oi = {}
    print("🐳 ПОИСК КРУПНЫХ КИТОВ ЗАПУЩЕН (ФРАНКФУРТ)...", flush=True)
    
    while True:
        for s, limit in LIMITS.items():
            curr_oi, price = get_data(s)
            if curr_oi is not None:
                if s in history_oi:
                    diff = curr_oi - history_oi[s]
                    
                    # Фильтр: реагируем только на ОЧЕНЬ крупные суммы
                    if abs(diff) >= limit:
                        icon = "🟢" if diff > 0 else "🔴"
                        label = "КИТ ЗАШЕЛ" if diff > 0 else "КИТ ВЫШЕЛ"
                        # Если движение в 3 раза больше лимита - ставим значок кита
                        whale_icon = " 🐳🐳🐳" if abs(diff) > limit * 3 else ""
                        
                        print(f"[{time.strftime('%H:%M:%S')}] {icon} {s}: {price}$ | {label}: {diff/1e6:.2f} млн$ {whale_icon}", flush=True)
                
                history_oi[s] = curr_oi
        time.sleep(20)

if __name__ == "__main__":
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', 10000), QuietServer).serve_forever(), daemon=True).start()
    monitor()
