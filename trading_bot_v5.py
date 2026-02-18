import os, time, random, threading
from collections import deque
from fastapi import FastAPI

START_BALANCE = float(os.getenv("START_BALANCE", "10000"))
MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "3.0"))
RISK_PER_TRADE_PCT = float(os.getenv("RISK_PER_TRADE_PCT", "0.2"))
TAKER_FEE = float(os.getenv("TAKER_FEE", "0.0004"))
SLIPPAGE = float(os.getenv("SLIPPAGE", "0.0002"))
NOTIONAL_CAP_PCT = float(os.getenv("NOTIONAL_CAP_PCT", "0.20"))

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "8000"))

bot_running = False
bot_lock = threading.Lock()
bot_thread = None

TRADE_LOG_MAX = int(os.getenv("TRADE_LOG_MAX", "2000"))
trade_log = deque(maxlen=TRADE_LOG_MAX)

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
        dd = (self.peak - self.balance) / self.peak * 100 if self.peak > 0 else 0.0
        self.max_drawdown = max(self.max_drawdown, dd)
        self.equity_curve.append(self.balance)

        self.trades += 1
        self.last_pnl = pnl
        if pnl >= 0: self.wins += 1
        else: self.losses += 1

    def daily_loss_pct(self) -> float:
        return (self.daily_start - self.balance) / self.daily_start * 100 if self.daily_start > 0 else 0.0

    def win_rate(self) -> float:
        return (self.wins / self.trades * 100) if self.trades else 0.0

equity = EquityTracker(START_BALANCE)

def generate_fake_candles(n=80):
    candles = []
    price = 100.0 + random.uniform(-3, 3)
    for _ in range(n):
        drift = random.uniform(-0.15, 0.15)
        vol = random.uniform(0.6, 1.8)
        high = price + abs(random.uniform(0, vol)) + max(drift, 0)
        low = price - abs(random.uniform(0, vol)) + min(drift, 0)
        close = random.uniform(low, high)
        candles.append({"high": high, "low": low, "close": close})
        price = close
    return candles

def calculate_atr(candles, period=14):
    if len(candles) < period + 1: return None
    trs = []
    for i in range(1, len(candles)):
        h, l, pc = candles[i]["high"], candles[i]["low"], candles[i-1]["close"]
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))
    return sum(trs[-period:]) / period if len(trs) >= period else None

def calculate_position_size(balance: float, atr: float, entry_price: float) -> float:
    risk_amount = balance * (RISK_PER_TRADE_PCT / 100.0)
    if not atr or atr <= 0: return 0.0
    size = risk_amount / atr

    max_notional = balance * NOTIONAL_CAP_PCT
    max_size = max_notional / max(entry_price, 1e-9)
    return min(size, max_size)

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

def choose_side(candles):
    if len(candles) < 10: return random.choice(["LONG", "SHORT"])
    mom = candles[-1]["close"] - candles[-9]["close"]
    if mom > 0: return "LONG" if random.random() > 0.25 else "SHORT"
    return "SHORT" if random.random() > 0.25 else "LONG"

def trading_loop():
    global bot_running
    while True:
        with bot_lock:
            if not bot_running:
                break
        try:
            if equity.daily_loss_pct() >= MAX_DAILY_LOSS_PCT:
                with bot_lock:
                    bot_running = False
                break

            candles = generate_fake_candles()
            atr = calculate_atr(candles)
            if not atr:
                time.sleep(1)
                continue

            side = choose_side(candles)
            raw_entry = candles[-1]["close"]
            size = calculate_position_size(equity.balance, atr, raw_entry)
            if size <= 0:
                time.sleep(1)
                continue

            entry_px, _ = execute_trade(raw_entry, size, side)
            move = random.uniform(-atr * 2.0, atr * 2.0)
            exit_px = max(entry_px + move, 0.0001) if side == "LONG" else max(entry_px - move, 0.0001)
            pnl = close_trade(entry_px, exit_px, size, side)

            trade_log.append({
                "ts": time.time(),
                "symbol": "FAKEUSDT",
                "side": side,
                "entry": entry_px,
                "exit": exit_px,
                "size": size,
                "atr": atr,
                "pnl": pnl,
                "balance": equity.balance,
                "daily_loss_pct": equity.daily_loss_pct(),
                "drawdown": equity.max_drawdown,
            })

            time.sleep(2)

        except Exception:
            time.sleep(2)

def start_loop_thread():
    global bot_thread
    with bot_lock:
        if bot_thread and bot_thread.is_alive():
            return
        bot_thread = threading.Thread(target=trading_loop, daemon=True)
        bot_thread.start()

def snapshot():
    return {
        "running": bot_running,
        "balance": equity.balance,
        "drawdown": equity.max_drawdown,
        "daily_loss_pct": equity.daily_loss_pct(),
        "trades": equity.trades,
        "win_rate": equity.win_rate(),
        "last_pnl": equity.last_pnl,
        "port": PORT
    }

app = FastAPI(title="TradeMax Bot API", version="5.0")

@app.get("/")
def root():
    return {"ok": True, "hint": "Use /health or /api/health or /docs"}

@app.get("/health")
def health():
    return snapshot()

@app.get("/api/health")
def api_health():
    return snapshot()

@app.get("/equity")
def eq():
    return {"equity": equity.equity_curve[-2000:]}

@app.get("/api/equity")
def api_eq():
    return {"equity": equity.equity_curve[-2000:]}

@app.get("/trades")
def trades(limit: int = 200):
    limit = max(1, min(int(limit), 2000))
    data = list(trade_log)[-limit:]
    return {"trades": data, "count": len(data)}

@app.get("/api/trades")
def api_trades(limit: int = 200):
    return trades(limit)

@app.post("/start")
def start():
    global bot_running
    with bot_lock:
        bot_running = True
    start_loop_thread()
    return {"ok": True, **snapshot()}

@app.post("/stop")
def stop():
    global bot_running
    with bot_lock:
        bot_running = False
    return {"ok": True, **snapshot()}

@app.post("/reset")
def reset():
    global bot_running, equity, trade_log
    with bot_lock:
        bot_running = False
        equity = EquityTracker(START_BALANCE)
        trade_log = deque(maxlen=TRADE_LOG_MAX)
    return {"ok": True, **snapshot()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
