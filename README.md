# 🤖 AI Trading Bot v5.0

Binance Futures için gerçek zamanlı AI destekli trading botu.

## 🚀 Railway'de Deploy

### 1. GitHub Repository Oluştur

1. [GitHub](https://github.com) → **New repository**
2. İsim: `ai-trading-bot` (veya istediğin)
3. Public veya Private
4. **Create repository**

### 2. Dosyaları Yükle

Aşağıdaki 4 dosyayı repository'ye yükle:
- `trading_bot_v5.py`
- `requirements.txt`
- `Procfile`
- `railway.json`

**Terminal üzerinden:**

```bash
cd /Users/serkaneren/Desktop/trading-botv5
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/KULLANICI_ADIN/ai-trading-bot.git
git push -u origin main
```

### 3. Railway'de Deploy

1. [Railway](https://railway.app) → Sign up with GitHub
2. **New Project** → **Deploy from GitHub repo**
3. Repository'ni seç: `ai-trading-bot`
4. Deploy başlayacak (2-3 dakika)
5. **Settings** → **Networking** → **Generate Domain**
6. Domain oluşturulacak: `https://ai-trading-bot-production-XXXX.up.railway.app`

### 4. Bota Eriş

Railway size verdiği URL'yi tarayıcıda aç:
```
https://SENIN-DOMAIN.up.railway.app
```

Botu buradan kontrol edebilirsin!

## ⚙️ Risk Ayarları

Arayüzde en alttaki **Risk & Bot Ayarları** panelinden:
- Max pozisyon sayısı
- Pozisyon büyüklüğü
- Take Profit / Stop Loss
- Kaldıraç
- Sinyal eşikleri

Değiştir ve **💾 KAYDET** butonuna bas.

## 📊 Özellikler

✅ Gerçek Binance Futures verisi (82 coin)
✅ 5 AI stratejisi (Trend Following, Mean Reversion, Breakout, Scalping, VWAP)
✅ Teknik analiz: RSI, MACD, EMA, Bollinger, Stochastic, VWAP
✅ Canlı PnL grafiği (hover tooltip ile)
✅ Candlestick chart (TP/SL çizgileri)
✅ Risk metrikleri: Drawdown, Profit Factor
✅ Trade geçmişi filtreleme
✅ Strateji öğrenimi (kazanan stratejilerin skoru artar)

## 🔒 Güvenlik

⚠️ Bu bot **SİMÜLE** edilmiş trading yapar — gerçek para kullanmaz!
Gerçek para trading için kod değişikliği gerekir.

## 📝 Notlar

- Railway ücretsiz planda aylık $5 kredi var
- Bot 7/24 çalışır
- Logs için: Railway dashboard → Deployments → View Logs
- Bilgisayar kapalı bile olsa çalışır

## 🛠️ Sorun Giderme

**Bot başlamıyor:**
- Railway logs'u kontrol et
- Python versiyonu: 3.9+

**Bağlantı hatası:**
- Railway domain'in doğru mu kontrol et
- Settings → Networking → Public Networking açık olmalı

**Trade çekmiyor:**
- Risk ayarlarındaki "Min Sinyal Skoru"nu düşür (2'ye)
- "Tarama Büyüklüğü"nü artır (20'ye)
- Logs'a bak, hangi coinler analiz ediliyor

## 📞 Destek

Railway dashboard üzerinden logs takip edilebilir.
