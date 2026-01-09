import requests, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Настройки мониторинга
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
stats = {"longs": 0, "shorts": 0, "exit": 0}
market_data = {}

class TerminalDashboard(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        # Расчет индекса (имитация логики со скрина)
        total_move = stats['longs'] + stats['shorts'] + 0.1
        fear_greed = round((stats['longs'] / total_move) * 10, 2)
        warning = "КИTЫ СБРАСЫВАЮТ ПОЗИЦИИ" if stats['exit'] > stats['longs'] else "КИTЫ НАКАПЛИВАЮТ LONG"

        html = f"""
        <html><head><meta http-equiv="refresh" content="10">
        <style>
            body {{ background: #1a1a1a; color: #d4d4d4; font-family: 'Courier New', monospace; padding: 20px; font-size: 13px; }}
            .header {{ color: #aaa; border-bottom: 1px double #444; padding-bottom: 5px; }}
            .session {{ margin: 10px 0; font-weight: bold; }}
            .green {{ color: #00ff88; }} .red {{ color: #ff4444; }} .yellow {{ color: #ffd700; }}
            .alert {{ background: #ff7b7b; color: black; padding: 3px 10px; font-weight: bold; display: inline-block; margin: 10px 0; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; border-top: 1px dashed #555; border-bottom: 1px dashed #555; }}
            th {{ text-align: left; padding: 8px 0; color: #888; border-bottom: 1px solid #333; }}
            td {{ padding: 8px 0; }}
            .footer {{ margin-top: 15px; color: #aaa; font-style: italic; }}
        </style></head><body>
            <div class="header">🏛 ALL-IN-ONE TERMINAL | {time.strftime('%H:%M:%S')}</div>
            <div class="session">
                📊 СЕССИЯ: &nbsp; LONGS: <span class="green">${stats['longs']/1e6:.1f}M</span> 
                | SHORTS: <span class="red">${stats['shorts']/1e6:.1f}M</span> 
                | EXIT: <span class="yellow">${stats['exit']/1e6:.1f}M</span>
            </div>
            <div class="alert">⚠️ ВНИМАНИЕ: ИНДЕКС ЖАДНОСТИ {fear_greed} - {warning}</div>
            
            <table>
                <tr>
                    <th>Монета</th><th>Bid (Buy)</th><th>Ask (Sell)</th><th>Spread</th>
                    <th>Вход LONG</th><th>Вход SHORT</th><th>Exit 1m</th><th>Всего OI</th>
                </tr>
        """
        for s in SYMBOLS:
            d = market_data.get(s, {})
            if not d: continue
            html += f"""
                <tr>
                    <td><b>{s[:3]}</b></td>
                    <td>{d['bid']:.2f}</td><td>{d['ask']:.2f}</td>
                    <td>{d['spread']:.4f}%</td>
                    <td class="green">+{d['l_in']:.0f}k$</td>
                    <td class="red">+{d['s_in']:.0f}k$</td>
                    <td class="yellow">{d['exit']:.0f}k$</td>
                    <td>$ {d['total_oi']/1e6:.1f}M</td>
                </tr>
            """
        
        html += """
            </table>
            <div class="footer">💡 СОВЕТ: Если Вход LONG большой, а Spread растет — киты выкупают лимитные заявки продавцов.</div>
        </body></html>
        """
        self.wfile.write(html.encode('utf-8'))
    def log_message(self, format, *args): return

def monitor():
    global market_data, stats
    history_oi = {}
    while True:
        for s in SYMBOLS:
            try:
                # Получаем стакан для спреда и цену
                book = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/bookTicker?symbol={s}").json()
                oi_data = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={s}").json()
                
                bid, ask = float(book['bidPrice']), float(book['askPrice'])
                price = (bid + ask) / 2
                oi_usd = float(oi_data['openInterest']) * price
                spread = ((ask - bid) / ask) * 100

                l_in, s_in, ex = 0, 0, 0
                if s in history_oi:
                    diff = oi_usd - history_oi[s]
                    if diff > 10000: # Вход
                        if spread < 0.005: l_in = diff / 1000; stats['longs'] += diff
                        else: s_in = diff / 1000; stats['shorts'] += diff
                    elif diff < -10000: # Выход
                        ex = abs(diff) / 1000; stats['exit'] += abs(diff)

                market_data[s] = {
                    "bid": bid, "ask": ask, "spread": spread,
                    "l_in": l_in, "s_in": s_in, "exit": ex, "total_oi": oi_usd
                }
                history_oi[s] = oi_usd
            except: pass
        time.sleep(15)

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    HTTPServer(('0.0.0.0', 10000), TerminalDashboard).serve_forever()
