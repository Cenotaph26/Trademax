import time
import math
import random
from collections import deque
from fastapi import FastAPI
import uvicorn
import threading

# =========================
# CONFIG
# =========================

START_BALANCE = 10000
MAX_DAILY_LOSS_PCT = 3.0
RISK_PER_TRADE_PCT = 0.5
TAKER_FEE = 0.0004
SLIPPAGE = 0.0002

# =========================
# EQUITY TRACKER
# =========================

class EquityTracker:
    def __init__(self, starting_balance):
        self.start_balance = starting_balance
        self.balance = starting_balance
        self.peak = starting_balance
        self.daily_start = starting_balance
        self.max_drawdown = 0
        self.equity_curve = []
        self.last_day = time.strftime("%Y-%m-%d")

    def update(self, pnl):
        today = time.strftime("%Y-%m-%d")
        if today != self.last_day:
            self.daily_start = self.balance
            self.last_day = today

        self.balance += pnl
        self.peak = max(self.peak, self.balance)

        dd = (self.peak - self.balance) / self.peak * 100
        self.max_drawdown = max(self.max_drawdown, dd)

        self.equity_curve.append(self.balance)

    def daily_loss_pct(self):
        return (self.daily_start - self.balance) / self.daily_start * 100


equity = EquityTracker(START_BALANCE)

# =========================
# ATR HESAP
# =========================

def calculate_atr(candles, period=14):
    if len(candles) < period + 1:
        return None

    trs = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i-1]["close"]

        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

    return sum(trs[-period:]) / period


# =========================
# POSITION SIZE
# =========================

def calculate_position_size(balance, atr):
    risk_amount = balance * (RISK_PER_TRADE_PCT / 100)
    stop_distance = atr
    if stop_distance == 0:
        return 0
    size = risk_amount / stop_distance
    return size


# =========================
# TRADE EXECUTION
# =========================

def execute_trade(entry_price, size, side):
    slippage_adj = entry_price * SLIPPAGE

    if side == "LONG":
        entry_price += slippage_adj
    else:
        entry_price -= slippage_adj

    fee = entry_price * size * TAKER_FEE
    return entry_price, fee


def close_trade(entry_price, exit_price, size, side):
    if side == "LONG":
        pnl = (exit_price - entry_price) * size
    else:
        pnl = (entry_price - exit_price) * size

    fee = exit_price * size * TAKER_FEE
    pnl -= fee

    equity.update(pnl)
    return pnl


# =========================
# SIMPLE PAPER TRADE LOOP
# =========================

bot_running = True

def generate_fake_candles():
    candles = []
    price = 100
    for _ in range(50):
        high = price + random.uniform(0, 2)
        low = price - random.uniform(0, 2)
        close = random.uniform(low, high)
        candles.append({"high": high, "low": low, "close": close})
        price = close
    return candles


def trading_loop():
    global bot_running

    while bot_running:

        if equity.daily_loss_pct() >= MAX_DAILY_LOSS_PCT:
            print("⚠️ Max daily loss reached. Bot stopped.")
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

        entry, entry_fee = execute_trade(entry, size, side)

        # Fake price move
        move = random.uniform(-atr * 2, atr * 2)
        exit_price = entry + move if side == "LONG" else entry - move

        pnl = close_trade(entry, exit_price, size, side)

        print(f"Trade {side} | PnL: {round(pnl,2)} | Balance: {round(equity.balance,2)}")

        time.sleep(2)


# =========================
# FASTAPI
# =========================

app = FastAPI()

@app.get("/health")
def health():
    return {
        "balance": equity.balance,
        "drawdown": equity.max_drawdown,
        "daily_loss_pct": equity.daily_loss_pct(),
        "running": bot_running
    }

@app.get("/equity")
def equity_curve():
    return {"equity": equity.equity_curve}


# =========================
# START
# =========================

def start_bot():
    thread = threading.Thread(target=trading_loop)
    thread.daemon = True
    thread.start()


if __name__ == "__main__":
    start_bot()
    uvicorn.run(app, host="0.0.0.0", port=8000)
