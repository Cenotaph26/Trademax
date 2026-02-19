#!/usr/bin/env python3
import os, time, json, threading, requests, random
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# ===== Railway PORT =====
PORT = int(os.environ.get("PORT", 8787))

# ===== Config =====
CONFIG = {
    "timeframe": "5m",
    "start_balance": float(os.environ.get("START_BALANCE", "1000")),
    "scan_interval_sec": 10,
    "max_positions": int(os.environ.get("MAX_POSITIONS", "5")),
    # Trade açmayı kolaylaştırmak için eşiği biraz indirdim:
    "confidence_threshold": int(os.environ.get("CONF_THR", "60")),
    "volatility_threshold": float(os.environ.get("VOL_THR", "0.001")),
    # Rate limit koruma:
    "scan_symbols_limit": int(os.environ.get("SCAN_LIMIT", "40")),
}

BASE_URL = "https://testnet.binancefuture.com" if os.environ.get("TESTNET", "true").lower() == "true" else "https://fapi.binance.com"

STATE = {
    "mode": "AI_TESTNET_SIM",
    "balance": CONFIG["start_balance"],
    "positions": [],
    "wins": 0,
    "losses": 0,
    "learning_bias": 1.0,
    "last_scan": None,
    "last_signal": None,
    "symbols_scanned": 0,
}

# ===== Simple HTML Dashboard =====
DASHBOARD_HTML = r"""<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Trademax — AI Bot Dashboard</title>
  <style>
    :root { color-scheme: dark; }
    body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto; background:#0b0f17; color:#e7eefc; }
    .wrap { max-width: 1100px; margin: 0 auto; padding: 20px; }
    .top { display:flex; gap:12px; align-items:center; justify-content:space-between; flex-wrap:wrap; }
    .brand { font-weight:700; letter-spacing: .2px; }
    .pill { display:inline-flex; gap:8px; align-items:center; padding:8px 12px; background:#121a2a; border:1px solid #24314d; border-radius:999px; }
    .grid { display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap:12px; margin-top:14px; }
    .card { background:#0f1626; border:1px solid #24314d; border-radius:14px; padding:14px; }
    .k { font-size:12px; opacity:.75; }
    .v { font-size:20px; margin-top:6px; font-weight:700; }
    .row { display:flex; gap:12px; margin-top:12px; flex-wrap:wrap; }
    .panel { flex: 1 1 520px; }
    table { width:100%; border-collapse: collapse; overflow:hidden; border-radius:12px; border:1px solid #24314d; }
    th, td { padding:10px 10px; border-bottom:1px solid #1f2a45; font-size:13px; }
    th { text-align:left; color:#b7c6e6; background:#0d1424; position:sticky; top:0; }
    tr:hover td { background:#0d1424; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
    .ok { color:#39d98a; }
    .bad { color:#ff5c7a; }
    .muted { opacity:.7; }
    .foot { margin-top:14px; font-size:12px; opacity:.7; }
    @media (max-width: 900px) { .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div class="brand">Trademax <span class="muted">/ AI Bot Dashboard</span></div>
      <div class="pill"><span class="mono">/api/status</span> <span id="statusDot" class="ok">●</span> <span id="lastScan" class="muted">—</span></div>
    </div>

    <div class="grid">
      <div class="card"><div class="k">Mode</div><div class="v mono" id="mode">—</div></div>
      <div class="card"><div class="k">Balance</div><div class="v" id="balance">—</div></div>
      <div class="card"><div class="k">Positions</div><div class="v" id="posCount">—</div></div>
      <div class="card"><div class="k">Win / Loss</div><div class="v" id="wl">—</div></div>
    </div>

    <div class="row">
      <div class="panel card">
        <div class="k">Open Positions</div>
        <div style="margin-top:10px; max-height: 360px; overflow:auto;">
          <table>
            <thead>
              <tr>
                <th>Symbol</th><th>Dir</th><th>Entry</th><th>Qty</th><th>Lev</th><th>Conf</th><th>Time</th>
              </tr>
            </thead>
            <tbody id="posBody">
              <tr><td colspan="7" class="muted">No positions</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="panel card">
        <div class="k">Live Debug</div>
        <pre id="raw" class="mono" style="margin-top:10px; white-space:pre-wrap; word-break:break-word; font-size:12px; line-height:1.4; opacity:.9;"></pre>
      </div>
    </div>

    <div class="foot">Auto-refresh: 2s • Eğer burada veri geliyorsa bot çalışıyordur. Trade açmıyorsa eşikleri düşürmek gerekir.</div>
  </div>

<script>
async function tick(){
  try{
    const r = await fetch('/api/status', {cache:'no-store'});
    const j = await r.json();
    document.getElementById('statusDot').className='ok';
    document.getElementById('mode').textContent = j.mode ?? '—';
    document.getElementById('balance').textContent = (j.balance ?? 0).toFixed ? j.balance.toFixed(2) : j.balance;
    document.getElementById('posCount').textContent = (j.positions?.length ?? 0);
    document.getElementById('wl').textContent = `${j.wins ?? 0} / ${j.losses ?? 0}`;
    document.getElementById('lastScan').textContent = j.last_scan ? ('Last scan: ' + j.last_scan) : '—';

    // positions table
    const body = document.getElementById('posBody');
    const pos = j.positions || [];
    if(pos.length === 0){
      body.innerHTML = `<tr><td colspan="7" class="muted">No positions</td></tr>`;
    } else {
      body.innerHTML = pos.map(p => `
        <tr>
          <td class="mono">${p.symbol}</td>
          <td>${p.direction}</td>
          <td class="mono">${Number(p.entry).toFixed(4)}</td>
          <td class="mono">${Number(p.qty).toFixed(6)}</td>
          <td class="mono">${p.leverage ?? '-'}</td>
          <td class="mono">${p.confidence ?? '-'}</td>
          <td class="mono">${(p.time||'').replace('T',' ').replace('Z','')}</td>
        </tr>
      `).join('');
    }

    document.getElementById('raw').textContent = JSON.stringify(j, null, 2);
  }catch(e){
    document.getElementById('statusDot').className='bad';
  }
}
tick();
setInterval(tick, 2000);
</script>
</body>
</html>
"""

# ===== Binance data helpers =====
class BinanceData:
    def get_exchange_info(self):
        try:
            r = requests.get(f"{BASE_URL}/fapi/v1/exchangeInfo", timeout=12)
            return r.json()
        except:
            return None

    def get_usdt_symbols(self):
        info = self.get_exchange_info()
        if not info:
            return ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        syms = []
        for s in info.get("symbols", []):
            if s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING":
                syms.append(s["symbol"])
        return syms or ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    def get_price(self, symbol):
        try:
            r = requests.get(f"{BASE_URL}/fapi/v1/ticker/price", params={"symbol": symbol}, timeout=5)
            return float(r.json()["price"])
        except:
            return None

    def get_klines(self, symbol, limit=60):
        try:
            r = requests.get(
                f"{BASE_URL}/fapi/v1/klines",
                params={"symbol": symbol, "interval": CONFIG["timeframe"], "limit": limit},
                timeout=8
            )
            d = r.json()
            closes = [float(x[4]) for x in d]
            highs  = [float(x[2]) for x in d]
            lows   = [float(x[3]) for x in d]
            vols   = [float(x[5]) for x in d]
            return closes, highs, lows, vols
        except:
            return [], [], [], []

data = BinanceData()

# ===== AI =====
def analyze_symbol(symbol):
    closes, highs, lows, vols = data.get_klines(symbol)
    if len(closes) < 30:
        return None

    price = closes[-1]
    sma20 = sum(closes[-20:]) / 20.0
    volat = (max(highs[-20:]) - min(lows[-20:])) / max(price, 1e-9)
    vol_avg = sum(vols[-20:]) / 20.0
    vol_score = (vols[-1] / (vol_avg + 1e-9))

    trend_strength = abs(price - sma20) / max(price, 1e-9)

    # Confidence: trend + volatility + volume + learning bias
    confidence = (trend_strength * 100.0 + volat * 80.0 + vol_score * 5.0) * STATE["learning_bias"]
    confidence = int(max(1, min(95, confidence)))

    direction = "LONG" if price > sma20 else "SHORT"
    return {
        "symbol": symbol,
        "price": price,
        "confidence": confidence,
        "direction": direction,
        "volatility": volat,
    }

def dynamic_leverage(conf):
    # 1x..10x AI control
    if conf < 60: return 1
    if conf < 70: return 3
    if conf < 80: return 5
    if conf < 90: return 7
    return 10

def update_learning(pnl):
    if pnl > 0:
        STATE["wins"] += 1
        STATE["learning_bias"] *= 1.02
    else:
        STATE["losses"] += 1
        STATE["learning_bias"] *= 0.97
    STATE["learning_bias"] = max(0.5, min(1.5, STATE["learning_bias"]))

def open_position(sig):
    if len(STATE["positions"]) >= CONFIG["max_positions"]:
        return
    lev = dynamic_leverage(sig["confidence"])
    risk_amount = STATE["balance"] * 0.01  # %1
    qty = (risk_amount * lev) / max(sig["price"], 1e-9)

    STATE["positions"].append({
        "symbol": sig["symbol"],
        "entry": sig["price"],
        "direction": sig["direction"],
        "qty": qty,
        "leverage": lev,
        "confidence": sig["confidence"],
        "time": datetime.utcnow().isoformat()
    })
    STATE["last_signal"] = {"symbol": sig["symbol"], "confidence": sig["confidence"], "direction": sig["direction"], "time": datetime.utcnow().isoformat()}

def manage_positions():
    # Simple TP/SL for simulation
    for pos in list(STATE["positions"]):
        price = data.get_price(pos["symbol"])
        if not price:
            continue

        entry = pos["entry"]
        tp = entry * 1.02
        sl = entry * 0.99

        if pos["direction"] == "LONG":
            pnl = (price - entry) * pos["qty"]
            hit = price >= tp or price <= sl
        else:
            pnl = (entry - price) * pos["qty"]
            hit = price <= entry * 0.98 or price >= entry * 1.01

        if hit:
            STATE["balance"] += pnl
            update_learning(pnl)
            STATE["positions"].remove(pos)

def scanner_loop():
    symbols = data.get_usdt_symbols()
    while True:
        try:
            STATE["last_scan"] = datetime.utcnow().isoformat()

            scanned = 0
            for sym in symbols[:CONFIG["scan_symbols_limit"]]:
                scanned += 1
                sig = analyze_symbol(sym)
                if not sig:
                    continue

                if sig["confidence"] >= CONFIG["confidence_threshold"] and sig["volatility"] >= CONFIG["volatility_threshold"]:
                    open_position(sig)

            STATE["symbols_scanned"] = scanned
            manage_positions()
            time.sleep(CONFIG["scan_interval_sec"])
        except Exception as e:
            # keep alive
            time.sleep(3)

# ===== HTTP Handler =====
class Handler(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _html(self, html, code=200):
        b = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            return self._html(DASHBOARD_HTML)

        if self.path == "/health":
            return self._json({"ok": True, "ts": datetime.utcnow().isoformat()})

        if self.path == "/api/status":
            return self._json(STATE)

        return self._json({"error": "not_found"}, code=404)

def main():
    t = threading.Thread(target=scanner_loop, daemon=True)
    t.start()

    print(f"🚀 Trademax UI running on PORT {PORT} | BASE_URL={BASE_URL}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

if __name__ == "__main__":
    main()
