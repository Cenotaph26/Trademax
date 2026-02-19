import os
import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import pandas_ta as ta  # İndikatörler için
from fastapi import FastAPI
import uvicorn
import logging

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIG (Railway Variables üzerinden) ---
API_KEY = os.getenv('BINANCE_API_KEY', 'ANAHTAR_YOK')
SECRET_KEY = os.getenv('BINANCE_SECRET_KEY', 'ANAHTAR_YOK')
SYMBOL = 'BTC/USDT'
TIMEFRAME = '15m'

app = FastAPI()

# Canlı İzleme Verisi (Dashboard için)
bot_memory = {
    "balance": 0,
    "last_price": 0,
    "current_signal": "WAIT",
    "history": [],
    "error_log": None
}

# --- STRATEJİ MOTORU ---
def calculate_indicators(df):
    """Senin orijinal kodundaki tüm indikatör hesaplamaları burada."""
    df['RSI'] = ta.rsi(df['close'], length=14)
    df['EMA_20'] = ta.ema(df['close'], length=20)
    # Buraya senin kodundaki diğer indikatörleri ekleyebilirsin
    return df

async def trading_loop():
    """Ana Trade Döngüsü"""
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'enableRateLimit': True,
        'options': {'defaultType': 'future'} # Futures veya Spot tercihi
    })

    while True:
        try:
            # 1. Veri Çekme
            bars = await exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=100)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # 2. Analiz
            df = calculate_indicators(df)
            last_row = df.iloc[-1]
            bot_memory["last_price"] = last_row['close']
            
            # 3. Senin Sinyal Mantığın
            # ÖRNEK: RSI 30 altındaysa AL, 70 üstündeyse SAT
            if last_row['RSI'] < 30:
                bot_memory["current_signal"] = "BUY"
                # await exchange.create_market_buy_order(SYMBOL, 0.001)
            elif last_row['RSI'] > 70:
                bot_memory["current_signal"] = "SELL"
                # await exchange.create_market_sell_order(SYMBOL, 0.001)
            else:
                bot_memory["current_signal"] = "HOLD"

            logger.info(f"Fiyat: {bot_memory['last_price']} | RSI: {last_row['RSI']} | Sinyal: {bot_memory['current_signal']}")
            
            await asyncio.sleep(60) # 1 dakika bekle

        except Exception as e:
            bot_memory["error_log"] = str(e)
            logger.error(f"Döngü Hatası: {e}")
            await asyncio.sleep(30)

# --- WEB ARAYÜZÜ (UI) ---
@app.get("/")
async def dashboard():
    """Sitenize girince görünecek profesyonel özet."""
    return {
        "bot_name": "TradeMax AI v5",
        "system_status": "Active",
        "market": SYMBOL,
        "current_data": bot_memory,
        "api_connected": API_KEY != 'ANAHTAR_YOK'
    }

@app.on_event("startup")
async def start_event():
    asyncio.create_task(trading_loop())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
