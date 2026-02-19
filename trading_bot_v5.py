#!/usr/bin/env python3
"""AI Trading Bot v5.0 — Elite Dashboard - Enhanced with Risk Management"""

import random, time, json, threading, requests, math, os
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ── RISK MANAGEMENT & PERFORMANCE MODULES ──────────────────
try:
    from trading_bot_improvements import (
        BacktestEngine,
        RiskManager,
        StrategyOptimizer,
        PerformanceAnalyzer
    )
    ENHANCED_MODE = True
    print("🚀 Enhanced Trading Bot v5.0 - Risk Management Active")
except ImportError:
    ENHANCED_MODE = False
    print("📊 Standard Trading Bot v5.0 - Basic Mode")

# ── CONFIG ────────────────────────────────────────────────
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
    "paper_trading": True  # ⚠️ ŞU AN FAKE TRADE (GERÇEK DEĞİL)
}

# ── GLOBAL ENGINE ─────────────────────────────────────────
engine_g = None


# ── BINANCE DATA CLIENT (READ-ONLY) ───────────────────────
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


# ── SIMPLE AI AGENT (SIMULATION) ──────────────────────────
class TradingAgent:
    def __init__(self, balance):
        self.start_balance = balance
        self.balance = balance
        self.positions = []
        self.trade_log = []
        self.win = 0
        self.loss = 0
        self.drawdown = 0
        self.peak_balance = balance

    def open_position(self, symbol, price, side, confidence):
        if len(self.positions) >= CONFIG["max_positions"]:
            return

        risk_amount = self.balance * CONFIG["risk_per_trade"]
        qty = risk_amount / price

        position = {
            "symbol": symbol,
            "entry": price,
            "side": side,
            "qty": qty,
            "confidence": confidence,
            "time": datetime.utcnow().isoformat()
        }
        self.positions.append(position)

    def close_position(self, pos, price):
        pnl = 0
        if pos["side"] == "BUY":
            pnl = (price - pos["entry"]) * pos["qty"]
        else:
            pnl = (pos["entry"] - price) * pos["qty"]

        self.balance += pnl
        self.trade_log.append({
            "symbol": pos["symbol"],
            "pnl": pnl,
            "time": datetime.utcnow().isoformat()
        })

        if pnl > 0:
            self.win += 1
        else:
            self.loss += 1

        self.positions.remove(pos)

        # drawdown hesaplama
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
        dd = (self.peak_balance - self.balance) / self.peak_balance
        self.drawdown = max(self.drawdown, dd)


# ── STRATEGY ENGINE (BASIC AI SCORE) ──────────────────────
class StrategyEngine:
    def __init__(self):
        self.client = BinanceClient()
        self.agent = TradingAgent(CONFIG["initial_balance"])

    def analyze(self, symbol):
        closes, highs, lows = self.client.get_klines(symbol, CONFIG["timeframe"], 100)
        if not closes:
            return None

        price = closes[-1]
        sma = sum(closes[-20:]) / 20
        trend = "UP" if price > sma else "DOWN"

        volatility = (max(highs[-20:]) - min(lows[-20:])) / price
        confidence = min(95, int((abs(price - sma) / price) * 100 + volatility * 100))

        return {
            "symbol": symbol,
            "price": price,
            "trend": trend,
            "confidence": confidence
        }

    def maybe_trade(self, analysis):
        if not analysis:
            return

        if analysis["confidence"] < CONFIG["confidence_threshold"]:
            return

        side = "BUY" if analysis["trend"] == "UP" else "SELL"
        self.agent.open_position(
            analysis["symbol"],
            analysis["price"],
            side,
            analysis["confidence"]
        )

    def manage_positions(self):
        for pos in list(self.agent.positions):
            price = self.client.get_price(pos["symbol"])
            if not price:
                continue

            tp = pos["entry"] * (1 + CONFIG["tp_pct"])
            sl = pos["entry"] * (1 - CONFIG["sl_pct"])

            if pos["side"] == "BUY":
                if price >= tp or price <= sl:
                    self.agent.close_position(pos, price)
            else:
                if price <= pos["entry"] * (1 - CONFIG["tp_pct"]) or price >= pos["entry"] * (1 + CONFIG["sl_pct"]):
                    self.agent.close_position(pos, price)

    def loop(self):
        while True:
            try:
                for s in CONFIG["symbols"]:
                    analysis = self.analyze(s)
                    self.maybe_trade(analysis)

                self.manage_positions()
                time.sleep(CONFIG["scan_interval"])
            except Exception as e:
                print("Engine error:", e)
                time.sleep(2)


# ── HTTP DASHBOARD API ────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def _send(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        if self.path == "/api/debug":
            self._send({
                "balance": engine_g.agent.balance,
                "start_balance": engine_g.agent.start_balance,
                "positions": engine_g.agent.positions,
                "win": engine_g.agent.win,
                "loss": engine_g.agent.loss,
                "drawdown": engine_g.agent.drawdown,
                "paper_trading": CONFIG["paper_trading"]
            })
        else:
            self._send({"status": "running"})


# ── MAIN ─────────────────────────────────────────────────
def run():
    global engine_g
    engine_g = StrategyEngine()

    t = threading.Thread(target=engine_g.loop, daemon=True)
    t.start()

    server = HTTPServer(("0.0.0.0", 8787), Handler)
    print("🚀 Trading Bot v5 Dashboard running on http://localhost:8787")
    server.serve_forever()


if __name__ == "__main__":
    run()
