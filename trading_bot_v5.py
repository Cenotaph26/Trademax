#!/usr/bin/env python3
import os, time, math, json, threading, random, requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# ===== ENV CONFIG (RAILWAY UYUMLU) =====
PORT = int(os.environ.get("PORT", 8787))
API_KEY = os.environ.get("BINANCE_API_KEY", "")
API_SECRET = os.environ.get("BINANCE_API_SECRET", "")
TESTNET = os.environ.get("TESTNET", "true").lower() == "true"
MAX_LEVERAGE = int(os.environ.get("MAX_LEVERAGE", "10"))
START_BALANCE = float(os.environ.get("START_BALANCE", "1000"))
MAX_POSITIONS = int(os.environ.get("MAX_POSITIONS", "5"))

BASE_URL = "https://testnet.binancefuture.com" if TESTNET else "https://fapi.binance.com"

STATE = {
    "balance": START_BALANCE,
    "positions": [],
    "wins": 0,
    "losses": 0,
    "learning_bias": 1.0,
    "last_scan": None,
    "mode": "AI_TESTNET"
}

# ===== BINANCE DATA CLIENT =====
class BinanceData:
    def get_price(self, symbol):
        try:
            r = requests.get(f"{BASE_URL}/fapi/v1/ticker/price", params={"symbol": symbol}, timeout=5)
            return float(r.json()["price"])
        except:
            return None

    def get_klines(self, symbol, limit=50):
        try:
            r = requests.get(
                f"{BASE_URL}/fapi/v1/klines",
                params={"symbol": symbol, "interval": "5m", "limit": limit},
                timeout=5
            )
            data = r.json()
            closes = [float(c[4]) for c in data]
            highs = [float(c[2]) for c in data]
            lows = [float(c[3]) for c in data]
            volumes = [float(c[5]) for c in data]
            return closes, highs, lows, volumes
        except:
            return [], [], [], []

    def get_usdt_symbols(self):
        try:
            r = requests.get(f"{BASE_URL}/fapi/v1/exchangeInfo", timeout=10)
            data = r.json()
            return [
                s["symbol"] for s in data["symbols"]
                if s["quoteAsset"] == "USDT" and s["status"] == "TRADING"
            ]
        except:
            return ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

data_client = BinanceData()

# ===== AI ENGINE (ÖĞRENEN) =====
class AIEngine:
    def analyze(self, symbol):
        closes, highs, lows, volumes = data_client.get_klines(symbol)
        if len(closes) < 30:
            return None

        price = closes[-1]
        sma20 = sum(closes[-20:]) / 20
        volatility = (max(highs[-20:]) - min(lows[-20:])) / price
        volume_score = volumes[-1] / (sum(volumes[-20:]) / 20 + 1)

        trend_strength = abs(price - sma20) / price
        confidence = min(95, int((trend_strength * 100 + volatility * 80 + volume_score * 5) * STATE["learning_bias"]))

        direction = "LONG" if price > sma20 else "SHORT"

        return {
            "symbol": symbol,
            "price": price,
            "confidence": confidence,
            "direction": direction,
            "volatility": volatility
        }

    def dynamic_leverage(self, confidence):
        if confidence < 65:
            return 1
        elif confidence < 75:
            return 3
        elif confidence < 85:
            return 5
        else:
            return min(MAX_LEVERAGE, 10)

ai = AIEngine()

# ===== LEARNING SYSTEM =====
def update_learning(pnl):
    if pnl > 0:
        STATE["wins"] += 1
        STATE["learning_bias"] *= 1.02
    else:
        STATE["losses"] += 1
        STATE["learning_bias"] *= 0.97

    STATE["learning_bias"] = max(0.5, min(1.5, STATE["learning_bias"]))

# ===== POSITION MANAGEMENT (TESTNET SIMULATED EXECUTION) =====
def open_position(signal):
    if len(STATE["positions"]) >= MAX_POSITIONS:
        return

    leverage = ai.dynamic_leverage(signal["confidence"])
    risk_amount = STATE["balance"] * 0.01
    qty = (risk_amount * leverage) / signal["price"]

    STATE["positions"].append({
        "symbol": signal["symbol"],
        "entry": signal["price"],
        "direction": signal["direction"],
        "qty": qty,
        "leverage": leverage,
        "confidence": signal["confidence"],
        "time": datetime.utcnow().isoformat()
    })

def manage_positions():
    for pos in list(STATE["positions"]):
        price = data_client.get_price(pos["symbol"])
        if not price:
            continue

        pnl = 0
        if pos["direction"] == "LONG":
            pnl = (price - pos["entry"]) * pos["qty"]
        else:
            pnl = (pos["entry"] - price) * pos["qty"]

        tp = pos["entry"] * 1.02
        sl = pos["entry"] * 0.99

        if price >= tp or price <= sl:
            STATE["balance"] += pnl
            update_learning(pnl)
            STATE["positions"].remove(pos)

# ===== SCANNER LOOP (TÜM USDT COINLER) =====
def scanner():
    symbols = data_client.get_usdt_symbols()
    while True:
        try:
            STATE["last_scan"] = datetime.utcnow().isoformat()

            for sym in symbols[:60]:  # rate limit koruma
                signal = ai.analyze(sym)
                if not signal:
                    continue

                if signal["confidence"] > 72 and signal["volatility"] > 0.002:
                    open_position(signal)

            manage_positions()
            time.sleep(10)

        except Exception as e:
            print("SCANNER ERROR:", e)
            time.sleep(5)

# ===== DASHBOARD API =====
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"AI Futures Testnet Bot Running")

        elif self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

        elif self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(STATE).encode())

# ===== MAIN =====
def main():
    t = threading.Thread(target=scanner, daemon=True)
    t.start()

    print(f"🚀 AI Futures Testnet Bot Running on PORT {PORT}")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()

if __name__ == "__main__":
    main()
