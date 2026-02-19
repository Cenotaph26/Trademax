#!/usr/bin/env python3
import random, time, json, threading, requests, math, os
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── RAILWAY PORT FIX (EN KRİTİK) ──
PORT = int(os.environ.get("PORT", 8787))

CONFIG = {
    "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    "timeframe": "5m",
    "initial_balance": 1000.0,
    "risk_per_trade": 0.01,
    "max_positions": 3,
    "confidence_threshold": 65,
    "tp_pct": 0.018,
    "sl_pct": 0.009,
    "scan_interval": 5,
    "paper_trading": True
}

engine_g = None

# ── BINANCE CLIENT (DATA) ──
class BinanceClient:
    BASE = "https://fapi.binance.com"

    def get_price(self, symbol):
        try:
            r = requests.get(f"{self.BASE}/fapi/v1/ticker/price", params={"symbol": symbol}, timeout=5)
            return float(r.json()["price"])
        except:
            return None

    def get_klines(self, symbol, interval="5m", limit=100):
        try:
            r = requests.get(
                f"{self.BASE}/fapi/v1/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
                timeout=5
            )
            data = r.json()
            closes = [float(c[4]) for c in data]
            highs = [float(c[2]) for c in data]
            lows = [float(c[3]) for c in data]
            return closes, highs, lows
        except:
            return [], [], []

# ── AGENT ──
class TradingAgent:
    def __init__(self, balance):
        self.start_balance = balance
        self.balance = balance
        self.positions = []
        self.win = 0
        self.loss = 0

    def open_position(self, symbol, price, side, confidence):
        if len(self.positions) >= CONFIG["max_positions"]:
            return

        risk_amount = self.balance * CONFIG["risk_per_trade"]
        qty = risk_amount / price

        self.positions.append({
            "symbol": symbol,
            "entry": price,
            "side": side,
            "qty": qty,
            "confidence": confidence,
            "time": datetime.utcnow().isoformat()
        })

    def close_position(self, pos, price):
        if pos["side"] == "BUY":
            pnl = (price - pos["entry"]) * pos["qty"]
        else:
            pnl = (pos["entry"] - price) * pos["qty"]

        self.balance += pnl
        self.positions.remove(pos)

        if pnl > 0:
            self.win += 1
        else:
            self.loss += 1

# ── ENGINE ──
class StrategyEngine:
    def __init__(self):
        self.client = BinanceClient()
        self.agent = TradingAgent(CONFIG["initial_balance"])

    def analyze(self, symbol):
        closes, highs, lows = self.client.get_klines(symbol)
        if not closes:
            return None

        price = closes[-1]
        sma = sum(closes[-20:]) / 20
        trend = "BUY" if price > sma else "SELL"
        confidence = min(95, int(abs(price - sma) / price * 100 + random.randint(10, 40)))

        return {"symbol": symbol, "price": price, "trend": trend, "confidence": confidence}

    def loop(self):
        while True:
            try:
                for s in CONFIG["symbols"]:
                    analysis = self.analyze(s)
                    if analysis and analysis["confidence"] > CONFIG["confidence_threshold"]:
                        self.agent.open_position(
                            analysis["symbol"],
                            analysis["price"],
                            analysis["trend"],
                            analysis["confidence"]
                        )
                time.sleep(CONFIG["scan_interval"])
            except Exception as e:
                print("ENGINE ERROR:", e)
                time.sleep(2)

# ── API HANDLER ──
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Trading Bot Running")

        elif self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

        elif self.path == "/api/debug":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "balance": engine_g.agent.balance,
                "positions": engine_g.agent.positions,
                "win": engine_g.agent.win,
                "loss": engine_g.agent.loss,
                "paper_trading": CONFIG["paper_trading"]
            }).encode())

# ── MAIN ──
def run():
    global engine_g
    engine_g = StrategyEngine()

    thread = threading.Thread(target=engine_g.loop, daemon=True)
    thread.start()

    print(f"🚀 Railway Bot Running on PORT {PORT}")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()

if __name__ == "__main__":
    run()
