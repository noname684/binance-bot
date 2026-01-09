import requests, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Настройки мониторинга
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
data_log = [] # Список для хранения последних событий

class WebDashboard(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        # HTML-код страницы
        html = """
        <html><head>
            <meta http-equiv="refresh" content="30">
            <title>Whale Monitor</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f0f0f; color: #e0e0e0; padding: 30px; }
                .container { max-width: 900px; margin: auto; }
                h2 { color: #ffffff; border-bottom: 2px solid #333; padding-bottom: 10px; }
                table { width: 100%; border-collapse: collapse; margin-top: 20px; background: #1a1a1a; border-radius: 8px; overflow: hidden; }
                th { background: #2d2d2d; color: #aaa; text-align: left; padding: 15px; text-transform: uppercase; font-size: 12px; }
                td { padding: 15px; border-bottom: 1px solid #262626; font-size: 14px; }
                tr:hover { background: #252525; }
                .green { color: #00ff88; font-weight: bold; }
                .red { color: #ff4444; font-weight: bold; }
                .badge { padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
                .bg-green { background: rgba(0, 255, 136, 0.1); color: #00ff88; }
                .bg-red { background: rgba(255, 68, 68,
