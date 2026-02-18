import os
import time
import random
import threading
from collections import deque

# =========================
# CONFIG
# =========================
START_BALANCE = float(os.getenv("START_BALANCE", "10000"))
MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "3.0"))
RISK_PER_TRADE_PCT = float(os.getenv("RISK_PER_TRADE_PCT", "0.5"))
TAKER_FEE = float(os.getenv("TAKER_FEE", "0.0004"))
SLIPPAGE = float(os.getenv("SLIPPAGE", "0.0002"))

# Railway port: MUTLAKA env PORT kullan
PORT = int(os.getenv("PORT", "8000"))
HOST = "0.0.0.0"

# =========================
# EQUITY TRACKER
# =========================
class EquityTracker:
    def __init__(self, starting_balance: float):
        self.start_balance = starting_balance
        self.balance = starting_balance
        self.peak = starting_balance
        self.daily_start = starting_balance
        self.max_drawdown = 0.0
        self.equity_curve = []
        self.last_day = time.strftime("%Y-%m-%d")
        self.trades = 0
        self.wins = 0
        self.losses = 0
        self.last_pnl = 0.0

    def update(self, pnl: float):
        today = time.strftime("%Y-%m-%d")
        if today != self.last_day:
            self.daily_start = self.balance
            self.last_day = today

        self.balance += pnl
        self.peak = max(self.peak, self.balance)

        dd = (self.peak - self.balance) / self.peak * 100 if self.peak > 0 else 0
        self.max_drawdown = max(self.max_drawdown, dd)

        self.equity_curve.append(self.balance)

        self.trades += 1
        self.last_pnl = pnl
        if pnl >= 0:
            self.wins += 1
        else:
            self.losses += 1

    def daily_loss_pct(self) -> float:
        if self.daily_start <= 0:
            return 0.0
        return (self.daily_start - self.balance) / self.daily_start * 100

equity = EquityTracker(START_BALANCE)

# =========================
# ATR
# =========================
def calculate_atr(candles, period=14):
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        h = candles[i]["high"]
        l = candles[i]["low"]
        pc = candles[i - 1]["close"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    return sum(trs[-period:]) / period if len(trs) >= period else None

# =========================
# POSITION SIZE
# =========================
def calculate_position_size(balance: float, atr: float) -> float:
    # risk $ = balance * RISK_PER_TRADE_PCT
    risk_amount = balance * (RISK_PER_TRADE_PCT / 100.0)
    stop_distance = atr
    if not stop_distance or stop_distance <= 0:
        return 0.0
    return risk_amount / stop_distance

# =========================
# EXECUTION (paper)
# =========================
def execute_trade(entry_price: float, size: float, side: str):
    slip = entry_price * SLIPPAGE
    px = entry_price + slip if side == "LONG" else entry_price - slip
    fee = px * size * TAKER_FEE
    return px, fee

def close_trade(entry_price: float, exit_price: float, size: float, side: str):
    pnl = (exit_price - entry_price) * size if side == "LONG" else (entry_price - exit_price) * size
    fee = exit_price * size * TAKER_FEE
    pnl -= fee
    equity.update(pnl)
    return pnl

# =========================
# BOT LOOP
# =========================
bot_running = True

def generate_fake_candles():
    candles = []
    price = 100.0
    for _ in range(60):
        high = price + random.uniform(0, 2)
        low = price - random.uniform(0, 2)
        close = random.uniform(low, high)
        candles.append({"high": high, "low": low, "close": close})
        price = close
    return candles

def trading_loop():
    global bot_running
    print("BOT: started paper trading loop")

    while bot_running:
        try:
            # Risk kill-switch
            if equity.daily_loss_pct() >= MAX_DAILY_LOSS_PCT:
                print("RISK: Max daily loss reached -> stopping bot")
                bot_running = False
                break

            candles = generate_fake_candles()
            atr = calculate_atr(candles)

            if not atr:
                time.sleep(1)
                continue

            side = random.choice(["LONG", "SHORT"])
            entry = candles[-1]["close"]

            size = calculate_position_size(equity.balance, atr)
            if size <= 0:
                time.sleep(1)
                continue

            entry_px, entry_fee = execute_trade(entry, size, side)

            # Fake exit
            move = random.uniform(-atr * 2, atr * 2)
            exit_px = entry_px + move if side == "LONG" else entry_px - move

            pnl = close_trade(entry_px, exit_px, size, side)

            wr = (equity.wins / equity.trades * 100) if equity.trades else 0
            print(f"TRADE {side} pnl={pnl:.2f} bal={equity.balance:.2f} dd={equity.max_drawdown:.2f}% wr={wr:.1f}%")

            time.sleep(2)

        except Exception as e:
            # asla crash etmesin
            print("ERROR in trading_loop:", repr(e))
            time.sleep(2)

def start_bot_thread():
    t = threading.Thread(target=trading_loop, daemon=True)
    t.start()

# =========================
# API (FastAPI varsa, yoksa fallback)
# =========================
def build_app():
    try:
        from fastapi import FastAPI
        app = FastAPI()

        @app.get("/health")
        def health():
            wr = (equity.wins / equity.trades * 100) if equity.trades else 0
            return {
                "running": bot_running,
                "balance": equity.balance,
                "drawdown": equity.max_drawdown,
                "daily_loss_pct": equity.daily_loss_pct(),
                "trades": equity.trades,
                "win_rate": wr,
                "last_pnl": equity.last_pnl,
            }

        @app.get("/equity")
        def eq():
            return {"equity": equity.equity_curve[-2000:]}  # limit

        return app, "fastapi"

    except Exception as e:
        print("WARN: FastAPI not available, fallback mode:", repr(e))
        return None, "none"

def run_server(app, mode):
    if mode == "fastapi":
        import uvicorn
        uvicorn.run(app, host=HOST, port=PORT, log_level="info")
    else:
        # Railway health check için min HTTP server
        from http.server import BaseHTTPRequestHandler, HTTPServer
        import json

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith("/health"):
                    wr = (equity.wins / equity.trades * 100) if equity.trades else 0
                    payload = {
                        "running": bot_running,
                        "balance": equity.balance,
                        "drawdown": equity.max_drawdown,
                        "daily_loss_pct": equity.daily_loss_pct(),
                        "trades": equity.trades,
                        "win_rate": wr,
                        "last_pnl": equity.last_pnl,
                    }
                    data = json.dumps(payload).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write(b"ok")

        HTTPServer((HOST, PORT), H).serve_forever()

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    print(f"BOOT: balance={START_BALANCE} port={PORT}")
    start_bot_thread()
    app, mode = build_app()
    run_server(app, mode)
