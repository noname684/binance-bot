import requests, time, threading, os, json
from http.server import HTTPServer, BaseHTTPRequestHandler
from websocket import WebSocketApp

SYMBOLS = ["btcusdt", "ethusdt"]
# Глобальное хранилище данных
data_store = {s.upper(): {
    "p":0.0, "ls":0.0, "tb":0.0, "ts":0.0, "l":0.0, "sh":0.0, "ex":0.0, "liq":0.0, "oi":0.0
} for s in SYMBOLS}

# --- ПОТОК WEBSOCKET: ВСЕ ДАННЫЕ СРАЗУ ---
def on_message(ws, message):
    msg = json.loads(message)
    data = msg.get('data', {})
    event = data.get('e')
    symbol = data.get('s')

    if not symbol or symbol not in data_store: return

    # 1. Обновление цены (из тикера)
    if event == '24hrTicker':
        data_store[symbol]["p"] = float(data.get('c', 0))
    
    # 2. Обновление покупок/продаж (из агрегированных сделок)
    elif event == 'aggTrade':
        val = float(data.get('q', 0)) * float(data.get('p', 0))
        if data.get('m'): # m=True значит продажа (Taker Sell)
            data_store[symbol]["ts"] += val
        else: # Taker Buy
            data_store[symbol]["tb"] += val

    # 3. Ликвидации (в реальном времени)
    elif event == 'forceOrder':
        order = data.get('o', {})
        liq_val = float(order.get('q', 0)) * float(order.get('p', 0))
        data_store[symbol]["liq"] += liq_val

def run_ws():
    # Подписываемся на тикеры, сделки и ликвидации всех монет в одном соединении
    streams = []
    for s in SYMBOLS:
        streams.append(f"{s}@ticker")
        streams.append(f"{s}@aggTrade")
        streams.append(f"{s}@forceOrder")
    
    url = f"wss://fstream.binance.com/stream?streams={'/'.join(streams)}"
    ws = WebSocketApp(url, on_message=on_message)
    while True:
        ws.run_forever()
        time.sleep(5)

# --- РЕДКИЙ ПОТОК ДЛЯ OI (РАЗ В 2 МИНУТЫ) ---
def fetch_oi_slowly():
    while True:
        for s in data_store:
            try:
                r = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=10).json()
                data_store[s]["oi"] = float(r['openInterest']) * data_store[s]["p"]
                time.sleep(30) # Огромная пауза между монетами
            except: time.sleep(60)
        time.sleep(120)

# --- ИНТЕРФЕЙС ---
class UI(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers()
        rows = ""
        for s, d in data_store.items():
            total = d['tb'] + d['ts']
            pres = ((d['tb'] - d['ts']) / total * 100) if total > 0 else 0
            rows += f"""<tr>
                <td style='color:#00ff88; font-size:24px;'><b>{s}</b></td>
                <td style='font-family:monospace; font-size:28px;'>{d['p']:,.2f}</td>
                <td style='color:{'#00ff88' if pres > 0 else '#ff4444'}; font-size:22px;'>{pres:+.1f}%</td>
                <td style='color:#00ff88;'>${d['tb']:,.0f}</td>
                <td style='color:#ff4444;'>${d['ts']:,.0f}</td>
                <td style='color:#ff0066; font-weight:bold;'>${d['liq']:,.0f}</td>
                <td style='color:#00d9ff;'>${d['oi']:,.0f}</td>
            </tr>"""
        self.wfile.write(f"<html><head><meta http-equiv='refresh' content='5'><style>body{{background:#000; color:#eee; font-family:sans-serif; padding:40px;}}table{{width:100%; border-collapse:collapse; background:#0a0a0a;}}th{{background:#111; padding:20px; color:#444; text-align:left;}}td{{padding:20px; border-bottom:1px solid #181818;}}</style></head><body><h1>WHALE RADAR v4.2 (FULL STREAM)</h1><table><tr><th>Symbol</th><th>Price</th><th>Press (Live)</th><th>Taker Buy</th><th>Taker Sell</th><th>Liquidations</th><th>OI USD</th></tr>{rows}</table></body></html>".encode())

threading.Thread(target=run_ws, daemon=True).start()
threading.Thread(target=fetch_oi_slowly, daemon=True).start()
HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), UI).serve_forever()
