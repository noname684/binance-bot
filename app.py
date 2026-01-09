import requests
import time

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
history_oi = {}

def get_data(symbol):
    try:
        url = f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}"
        p_url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
        
        # В Германии (Frankfurt) эти запросы пройдут!
        price = float(requests.get(p_url, timeout=10).json()['price'])
        oi = float(requests.get(url, timeout=10).json()['openInterest'])
        return oi * price, price
    except Exception as e:
        # Если будет ошибка, мы её увидим
        # print(f"Ошибка {symbol}: {e}", flush=True) 
        return None, None

# Добавили flush=True, чтобы текст сразу летел в логи Render
print("🚀 МОНИТОРИНГ BINANCE ЗАПУЩЕН (FRANKFURT)", flush=True)

while True:
    print(f"\n--- Проверка {time.strftime('%H:%M:%S')} ---", flush=True)
    for s in SYMBOLS:
        curr_oi, price = get_data(s)
        if curr_oi is not None:
            if s in history_oi:
                diff = curr_oi - history_oi[s]
                status = "📈 ВХОД" if diff > 50000 else "📉 ВЫХОД" if diff < -50000 else ""
                print(f"{s}: {price}$ | Изм. OI: {diff:,.0f}$ {status}", flush=True)
            else:
                print(f"{s}: {price}$ | База создана", flush=True)
            history_oi[s] = curr_oi
        else:
            print(f"❌ {s}: Нет данных", flush=True)
            
    time.sleep(30)
