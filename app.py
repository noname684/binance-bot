import requests
import time

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
history_oi = {}

def get_binance_futures_data(symbol):
    try:
        # Берем данные с фьючерсов (цена + открытый интерес)
        p_url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
        oi_url = f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}"
        
        price = float(requests.get(p_url, timeout=10).json()['price'])
        oi_raw = float(requests.get(oi_url, timeout=10).json()['openInterest'])
        
        return oi_raw * price, price
    except Exception as e:
        print(f"⚠️ Ошибка {symbol}: {e}")
        return None, None

print("🚀 СТАРТ МОНИТОРИНГА BINANCE (ГЕРМАНИЯ)...")

while True:
    print(f"\n--- {time.strftime('%H:%M:%S')} ---")
    for s in SYMBOLS:
        curr_oi, price = get_binance_futures_data(s)
        
        if curr_oi is not None:
            if s in history_oi:
                diff = curr_oi - history_oi[s]
                status = "🟢 ВХОД" if diff > 100000 else "🔴 ВЫХОД" if diff < -100000 else ""
                print(f"{s}: {price}$ | OI: {curr_oi/1e6:.1f}M$ | Изм: {diff:,.0f}$ {status}")
            else:
                print(f"{s}: {price}$ | База создана")
            history_oi[s] = curr_oi
            
    time.sleep(30)
