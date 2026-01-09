import requests, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Настройки
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
session_stats = {"longs": 0, "shorts": 0, "exit": 0}
current_assets = {} # Для хранения последних данных по каждой монете

class ProfessionalTerminal(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        # Считаем общую активность
        total = session_stats['longs'] + session_stats['shorts'] + 0.1
        ratio = (session_stats['longs'] / total) * 100

        html = f"""
        <html><head><meta http-equiv="refresh" content="15">
        <style>
            body {{ background: #121212; color: #d4d4d4; font-family: 'Courier New', monospace; padding: 25px; line-height: 1.5; }}
            .header {{ color: #888; border-bottom: 1px solid #333; padding-bottom: 10px; margin-bottom: 15px; }}
            .stats-bar {{ background: #1e1e1e; padding: 15px; border-radius: 5px; margin-bottom: 20px; border: 1px solid #333; }}
            .green {{ color: #4ec9b0; font-weight: bold; }}
            .red {{ color: #f44747; font-weight: bold; }}
            .yellow {{ color: #dcdba3; font-weight: bold; }}
            table {{ width: 100%; border-collapse: collapse; background: #1a1a1a; }}
            th {{ text-align: left; padding: 12px; color: #666; border-bottom: 2px solid #333; font-size: 12px; }}
            td {{ padding: 12px; border-bottom: 1px solid #252525; }}
            .whale {{ font-size: 18px; }}
        </style></head><body>
            <div class="header">STATION: FRANKFURT-DE | TERMINAL ACTIVE | {time.strftime('%H:%M:%S')}</div>
            
            <div class="stats-bar">
                📊 <b>УЧЕТ ЗА СЕССИЮ:</b> &nbsp; 
                ВХОД LONG: <span class="green">${session_stats['longs']/1e6:.2f}M</span> | 
                ВХОД SHORT: <span class="red">${session_stats['shorts']/1e6:.2f}M</span> | 
                ВЫХОД (EXIT): <span class="yellow">${session_stats['exit']/1e6:.2f}M</span>
                <br>
                <small style="color: #555;">Доминирование покупателей: {ratio:.1f}%</small>
            </div>

            <table>
                <tr>
                    <th>АКТИВ</th><th>ТЕКУЩАЯ ЦЕНА</th><th>ИЗМ. OI (ПОСЛЕДНЕЕ)</th><th>СТАТУС</th><th>ВСЕГО В РЫНКЕ</th>
                </tr>
        """
        
        # Выводим монеты строго по порядку
        for s in SYMBOLS:
            data = current_assets.get(s, {"price": 0, "diff": 0, "status": "WAITING", "total": 0})
            color = "green" if data['diff'] > 0 else "red" if data['diff'] < 0 else ""
            whale = "🐳" if abs(data['diff']) > 1000000 else ""
            
            html += f"""
                <tr>
                    <td><b>{s}</b></td>
                    <td>{data['price']:,.2f}$</td>
                    <td class="{color}">{data['diff']:+,.0f}$</td>
                    <td><b class="{color}">{data['status']}</b> {whale}</td>
                    <td>${data['total']/1e6:.1f}M</td>
                </tr>
            """
            
        html += """
            </table>
            <p style="color: #444; margin-top: 20px; font-size: 11px;">* Данные обновляются каждые 15 секунд. Фильтр шума: $30,000.</p>
        </body></html>
        """
        self.wfile.write(html.encode('utf-8'))
    def log_message(self, format, *args): return

def monitor():
    global current_assets, session_stats
    history_oi = {}
    while True:
        for s in SYMBOLS:
            try:
                # Получаем цену и Open Interest
                p_res = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={s}", timeout=5).json()
                oi_res = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}", timeout=5).json()
                
                price = float(p_res['price'])
                curr_oi_usd = float(oi_res['openInterest']) * price
                
                if s in history_oi:
                    diff = curr_oi_usd - history_oi[s]
                    
                    if abs(diff) > 30000: # Фильтр минимальных движений
                        status = "BUY_VOL" if diff > 0 else "SELL_VOL"
                        
                        # Обновляем глобальную статистику сессии
                        if diff > 0: session_stats['longs'] += diff
                        else: session_stats['shorts'] += abs(diff)
                        
                        # Сохраняем состояние для таблицы
                        current_assets[s] = {
                            "price": price, "diff": diff, 
                            "status": status, "total": curr_oi_usd
                        }
                else:
                    # Начальная инициализация
                    current_assets[s] = {"price": price, "diff": 0, "status": "START", "total": curr_oi_usd}
                
                history_oi[s] = curr_oi_usd
            except: pass
        time.sleep(15)

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    HTTPServer(('0.0.0.0', 10000), ProfessionalTerminal).serve_forever()
