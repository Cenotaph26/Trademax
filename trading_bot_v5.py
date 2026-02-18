import os
import time
import random
import threading
from collections import deque

# =========================
# CONFIG (Railway env destekli)
# =========================
START_BALANCE = float(os.getenv("START_BALANCE", "10000"))
MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "3.0"))  # örn 6.0 test için
RISK_PER_TRADE_PCT = float(os.getenv("RISK_PER_TRADE_PCT", "0.2"))   # 0.5 yerine 0.2 daha stabil
TAKER_FEE = float(os.getenv("TAKER_FEE", "0.0004"))
SLIPPAGE = float(os.getenv("SLIPPAGE", "0.0002"))
NOTIONAL_CAP_PCT = float(os.getenv("NOTIONAL_CAP_PCT", "0.20"))      # pozisyon notional max %20 balance

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "8000"))  # Railway mutlaka PORT verir

# =========================
# STATE
# =========================
bot_running = False
bot_lock = threading.Lock()
bot_thread = None

# =========================
# EQUITY + STATS
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
        self.last_trade_ts = None

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
        self.last_trade_ts = time.time()
        if pnl >= 0:
            self.wins += 1
        else:
            self.losses += 1

    def daily_loss_pct(self) -> float:
        if self.daily_start <= 0:
            return 0.0
        return (self.daily_start - self.balance) / self.daily_start * 100

    def win_rate(self) -> float:
        return (self.wins / self.trades * 100) if self.trades else 0.0


equity = EquityTracker(START_BALANCE)

# In-memory trade log (son N)
TRADE_LOG_MAX = int(os.getenv("TRADE_LOG_MAX", "2000"))
trade_log = deque(maxlen=TRADE_LOG_MAX)

# =========================
# ATR + MARKET SIM
# =========================
def generate_fake_candles(n=80):
    """
    Basit market simülasyonu (paper)
    İstersen burayı gerçek Binance verisiyle değiştireceğiz.
    """
    candles = []
    price = 100.0 + random.uniform(-3, 3)

    for _ in range(n):
        # rejim: bazen trend bazen range
        drift = random.uniform(-0.15, 0.15)
        vol = random.uniform(0.6, 1.8)

        high = price + abs(random.uniform(0, vol)) + max(drift, 0)
        low = price - abs(random.uniform(0, vol)) + min(drift, 0)
        close = random.uniform(low, high)

        candles.append({"high": high, "low": low, "close": close})
        price = close

    return candles


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
# RISK + EXECUTION (paper)
# =========================
def calculate_position_size(balance: float, atr: float, entry_price: float) -> float:
    """
    ATR stop_distance varsayımı.
    Risk $ = balance * RISK_PER_TRADE_PCT
    Size = risk$ / atr
    + Notional cap: max notional = balance * NOTIONAL_CAP_PCT
    """
    risk_amount = balance * (RISK_PER_TRADE_PCT / 100.0)
    stop_distance = atr

    if not stop_distance or stop_distance <= 0:
        return 0.0

    size = risk_amount / stop_distance

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


# =========================
# STRATEGY (baseline demo)
# =========================
def choose_side(candles):
    """
    Çok basit karar:
    son 8 candle momentum + küçük random.
    """
    if len(candles) < 10:
        return random.choice(["LONG", "SHORT"])

    last = candles[-1]["close"]
    prev = candles[-9]["close"]
    mom = last - prev

    if mom > 0:
        return "LONG" if random.random() > 0.25 else "SHORT"
    else:
        return "SHORT" if random.random() > 0.25 else "LONG"


# =========================
# BOT LOOP
# =========================
def trading_loop():
    global bot_running
    print(f"BOT: loop started | balance={equity.balance:.2f} | maxDailyLoss={MAX_DAILY_LOSS_PCT}%")

    while True:
        with bot_lock:
            if not bot_running:
                print("BOT: loop exit (bot_running=False)")
                break

        try:
            # Risk kill-switch
            if equity.daily_loss_pct() >= MAX_DAILY_LOSS_PCT:
                print(f"RISK: daily_loss_pct {equity.daily_loss_pct():.2f}% >= {MAX_DAILY_LOSS_PCT}% -> STOP")
                with bot_lock:
                    bot_running = False
                break

            candles = generate_fake_candles()
            atr = calculate_atr(candles)
            if not atr:
                time.sleep(1)
                continue

            symbol = "FAKEUSDT"
            side = choose_side(candles)

            raw_entry = candles[-1]["close"]
            size = calculate_position_size(equity.balance, atr, raw_entry)
            if size <= 0:
                time.sleep(1)
                continue

            entry_px, entry_fee = execute_trade(raw_entry, size, side)

            # Exit sim: ATR bazlı hareket
            move = random.uniform(-atr * 2.0, atr * 2.0)

            if side == "LONG":
                raw_exit = entry_px + move
            else:
                raw_exit = entry_px - move

            exit_px = max(raw_exit, 0.0001)
            pnl = close_trade(entry_px, exit_px, size, side)

            trade_log.append({
                "ts": time.time(),
                "symbol": symbol,
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

            print(f"TRADE {side} pnl={pnl:.2f} bal={equity.balance:.2f} dd={equity.max_drawdown:.2f}% "
                  f"dl={equity.daily_loss_pct():.2f}% wr={equity.win_rate():.1f}%")

            time.sleep(2)

        except Exception as e:
            print("ERROR in trading_loop:", repr(e))
            time.sleep(2)


def start_loop_thread():
    global bot_thread
    with bot_lock:
        if bot_thread and bot_thread.is_alive():
            return
        bot_thread = threading.Thread(target=trading_loop, daemon=True)
        bot_thread.start()


# =========================
# API (FastAPI varsa)
# =========================
def build_app():
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI(title="TradeMax Bot API", version="5.0")

    @app.get("/")
    def root():
        return {
            "ok": True,
            "service": "trading_bot_v5",
            "hint": "Use /health, /docs, /start, /stop, /reset, /trades, /equity"
        }

    @app.get("/health")
    def health():
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

    @app.get("/equity")
    def api_equity():
        return {"equity": equity.equity_curve[-2000:]}

    @app.get("/trades")
    def api_trades(limit: int = 200):
        limit = max(1, min(int(limit), 2000))
        data = list(trade_log)[-limit:]
        return {"trades": data, "count": len(data)}

    @app.post("/start")
    def api_start():
        global bot_running
        with bot_lock:
            bot_running = True
        start_loop_thread()
        return {"ok": True, "running": bot_running}

    @app.post("/stop")
    def api_stop():
        global bot_running
        with bot_lock:
            bot_running = False
        return {"ok": True, "running": bot_running}

    @app.post("/reset")
    def api_reset():
        global bot_running, equity, trade_log
        with bot_lock:
            bot_running = False
            equity = EquityTracker(START_BALANCE)
            trade_log = deque(maxlen=TRADE_LOG_MAX)
        return {"ok": True, "running": bot_running, "balance": equity.balance}

    return app


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    print(f"BOOT: starting | PORT={PORT} | START_BALANCE={START_BALANCE}")
    try:
        app = build_app()
    except Exception as e:
        # FastAPI/uvicorn yoksa crash olmasın:
        print("FATAL: FastAPI not available. Add fastapi+uvicorn to requirements.txt", repr(e))
        raise

    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
