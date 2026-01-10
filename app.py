import requests, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Настройки мониторинга
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
session_data = {
    "longs": 0, "shorts": 0, "start_time": time.time(),
    "history": {} 
}

# Улучшенная функция форматирования (B для миллиардов, M для миллионов, k для тысяч)
def format_currency(value):
    abs_val = abs(value)
    if abs_val >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    elif abs_val >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    elif abs_val >= 1_000:
        return f"{value / 1_000:.0f}k"
    else:
        return f"{value:.0f}"

class UltimateTerminal(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        total = session_data['longs'] + session_data['shorts'] + 0.1
        power = (session_data['longs'] / total) * 100
        color = "#ff4444" if power < 40 else "#00ff88" if power > 60 else "#ffd700"
        
        html = f"""
        <html><head><meta http-equiv="refresh" content="15">
        <style>
            body {{ background: #050505; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; padding: 20px; }}
            .panel {{ border: 1px solid #222; background: #0f0f0f; padding: 25px; border-radius: 15px; }}
            .index-val {{ font-size: 48px; font-weight: 900; color: {color}; }}
            .bar-bg {{ background: #1a1a1a; height: 10px; border-radius: 5px; margin: 20px 0; }}
            .bar-fill {{ background: {color}; height: 100%; width: {power}%; transition: 1.2s; box-shadow: 0 0 15px {color}; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 25px; }}
            th {{ text-align: left; font-size: 11px; color: #444; text-transform: uppercase; padding: 10px; }}
            td {{ padding: 15px 10px; border-bottom: 1px solid #111; font-size: 15px; }}
            .up {{ color: #00ff88; }} .down {{ color: #ff4444; }}
            .tag {{ font-size: 10px; padding: 4px 8px; border-radius: 4px; font-weight: bold; background: #1a1a1a; border: 1px solid #333; }}
        </style></head><body>
            <div class="panel">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="color:#444; font-size:12px; font-weight:bold;">POWER INDEX</span><br>
                        <span class="index-val">{power:.1f}%</span>
                    </div>
                    <div style="text-align:right;">
                        <span style="color:{color}; font-weight:bold; font-size:18px;">
