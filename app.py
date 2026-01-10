import requests, time, threading, os, json
import websocket # Нужно добавить 'websocket-client' в requirements.txt
from http.server import HTTPServer, BaseHTTPRequestHandler

SYMBOLS = ["btcusdt", "ethusdt"] # Маленькие буквы для Websocket
data_store = {s.upper(): {"p":0.0, "ls":0.0, "tb":0, "ts":0, "l":0, "sh":0, "ex":0, "oi":0} for s in SYMBOLS}

def on_message(ws, message):
    msg = json.loads(message)
    symbol = msg['s']
    price = float(msg['c'])
    data_store[symbol]["p"] = price

def run_ws():
    # Подключаемся к потоку цен сразу для всех монет
    streams = "/".join([f"{s}@ticker" for s in SYMBOLS])
    ws = websocket.WebSocketApp(f"wss://fstream.binance.com/ws/{streams}", on_message=on_message)
    ws.run_forever()

def fetch_rest_data():
    while True:
        for s in SYMBOLS:
            sym = s.upper()
            try:
                # Запрашиваем только то, что нельзя получить через WS
                ls_d = requests.get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={sym}&period=5m&limit=1", timeout=5).json()
                data_store[sym]["ls"] = float(ls_d[0]['longShortRatio']) if ls_d else 0
                time.sleep(5) # Очень редкие запросы, чтобы не забанили
            except: pass
        time.sleep(30)

# Запуск
threading.Thread(target=run_ws, daemon=True).start()
threading.Thread(target=fetch_rest_data, daemon=True).start()

class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers()
        rows = ""
        for s in data_store:
            d = data_store[s]
            p_str = f"{d['p']:,.2f}" if d['p'] > 0 else "<span style='color:orange;'>WS CONNECTING...</span>"
            rows += f"<tr><td>{s}</td><td style='font-size:24px;'>{p_str}</td><td>{d['ls']:.2f}</td></tr>"
        
        self.wfile.write(f"<html><head><meta http-equiv='refresh' content='5'></head><body style='background:#000;color:#eee;'><h1>RADAR v3.9 (WEBSOCKET)</h1><table>{rows}</table></body></html>".encode())

HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), WebHandler).serve_forever()
