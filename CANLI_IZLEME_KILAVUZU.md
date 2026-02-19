# 🔴 CANLI BOT İZLEME SİSTEMİ

## 🎯 Nasıl Çalışır?

Ben (Claude) artık botunuzu **gerçek zamanlı** izleyebilirim! Her 10 saniyede bir bot durumunu kaydediyorum ve siz sorduğunuzda:
- Anlık performans analizi
- Sorun tespiti
- İyileştirme önerileri
sunuyorum.

---

## 📦 Kurulum

### 1. Dosyaları GitHub'a Ekleyin
```bash
cd Trademax/

# Yeni dosyalar:
# - trading_bot_v5.py (güncellenmiş)
# - trading_bot_improvements.py (önceden eklendi)
# - live_bot_monitor.py (YENİ)

git add .
git commit -m "Canlı izleme sistemi eklendi"
git push
```

### 2. Railway Otomatik Deploy Eder

Log'larda göreceksiniz:
```
✅ Risk Management modülü yüklendi
🔴 Canlı izleme aktif - Claude sizi izliyor!
   API: /api/live-status, /api/live-analysis, /api/live-report
```

---

## 🔌 API Endpoints

Botunuz artık şu endpoint'lere sahip:

### 1. `/api/live-status` - Anlık Durum
```json
{
  "current": {
    "balance": 10530.23,
    "total_pnl": 530.23,
    "win_rate": 65.5,
    "drawdown_pct": 3.2,
    "open_positions": 2
  },
  "trend_10min": {
    "balance_change": 123.45,
    "balance_change_pct": 1.18
  }
}
```

### 2. `/api/live-analysis` - Detaylı Analiz
```json
{
  "status": "🟢 EXCELLENT",
  "health_score": 85,
  "current_state": { ... },
  "trends": { ... },
  "issues": [],
  "warnings": ["⚠️  Portfolio heat yükseliyor: 7.5%"],
  "quick_suggestions": ["Position size'ı küçült"]
}
```

### 3. `/api/live-report` - Metin Raporu
```
======================================================================
🔴 CANLI BOT ANALİZİ - 🟢 EXCELLENT
Sağlık Skoru: 85/100
======================================================================

📊 TEMEL METRİKLER
----------------------------------------------------------------------
Sermaye:          $10,530.23 (+5.30%)
Toplam Trade:     20 (13W / 7L)
Win Rate:         65.0%
Profit Factor:    2.45
Drawdown:         3.20%
...
```

### 4. `/api/snapshot` - Tek Snapshot
Anlık bir snapshot alır (izleme geçmişi olmadan)

---

## 💬 Bana Nasıl Sorarım?

Railway'de botunuz çalışırken, bana şöyle sorabilirsiniz:

### Örnek Sorular:

**"Botu incele"**
```
Ben API'den veri çekerim ve size:
- Mevcut durumu
- Sorunları
- Önerileri
detaylı şekilde sunarım
```

**"Win rate neden düşük?"**
```
API'den son trade'leri ve stratejileri analiz eder,
win rate'in neden düşük olduğunu bulur, çözüm önerir
```

**"Drawdown çok yüksek, ne yapmalıyım?"**
```
Risk yönetimi metriklerini inceler,
- Position size ayarı
- Stop loss mesafesi
- Max positions sayısı
gibi parametrelerde değişiklik önerir
```

**"Hangi parametreleri değiştirmeliyim?"**
```
Mevcut performansa bakarak:
- min_score
- min_conf
- position_size_pct
- tp_pct / sl_pct
için optimize değerler önerir
```

**"Sorun var mı?"**
```
Sistemdeki tüm uyarıları ve sorunları listeler,
kritiklik sırasına göre çözüm önerir
```

---

## 🎬 Örnek Kullanım

### Senaryo 1: Genel Kontrol
**Siz:** "Botu incele, nasıl gidiyor?"

**Ben:** 
```
🔴 CANLI BOT ANALİZİ

Railway'den veri çektim:
- Sağlık Skoru: 75/100 (İyi)
- Balance: $10,430 (+4.3%)
- Win Rate: 62% (20 trade)
- Drawdown: 5.2%

⚠️  Tespit Edilen Sorunlar:
1. Win rate düşüş trendinde (son 1 saatte -3%)
2. Portfolio heat 9.5% (limit: 10%)

💡 Öneriler:
1. min_score'u 4'ten 5'e çıkar (daha seçici ol)
2. Yeni pozisyon açma (heat zaten yüksek)
3. Position size'ı %9'dan %7'ye düşür
```

### Senaryo 2: Sorun Çözme
**Siz:** "Sürekli loss alıyorum, neden?"

**Ben:**
```
API'den son 20 trade'inizi analiz ettim:

🔍 Tespit:
- Son 20 trade: 7W/13L (Win rate: 35%)
- Loss sebepleri:
  * 8 trade: SL (erken stop out)
  * 3 trade: Smart Exit (yanlış timing)
  * 2 trade: TP (kar çok küçük)

📊 Detaylı Analiz:
- Stop loss çok dar: %0.8 (ortalama volatilite: %1.2)
- Entry konfidansı düşük: Ortalama 52% (limit: 50%)
- MACD ve RSI çelişiyor (zayıf onay)

💡 Çözüm:
1. Stop loss'u %0.8'den %1.5'e çıkar
2. min_conf'u 50'den 60'a çıkar
3. Confirmation sayısını 2'den 3'e çıkar
4. ATR'ye göre dinamik SL kullan
```

### Senaryo 3: Optimizasyon
**Siz:** "Daha fazla kar yapmalıyım, ne yapmalıyım?"

**Ben:**
```
Mevcut performansınız:
- Win Rate: 68% (iyi!)
- Profit Factor: 1.8 (orta)
- Sharpe Ratio: 1.2 (düşük)

🎯 Profit Factor'u İyileştirme:
Sorun: Kazançlar küçük ($42 ort), kayıplar büyük ($58 ort)

Çözüm:
1. Take Profit'i %2'den %3'e çıkar
2. Trailing Stop ekle (kar koruma)
3. Kar varken momentum kaybını erken tespit et

📈 Risk/Reward Optimizasyonu:
Şu an: 1:1.4 (zayıf)
Hedef: 1:2.5 (iyi)

Önerilen Değişiklikler:
- tp_pct: 2.0 → 3.0
- sl_pct: 0.8 → 1.0
- profit_protect: True (zaten aktif ✓)
- max_pnl_drawdown: 0.4 → 0.3 (daha sıkı)
```

---

## 🔧 Monitoring Nasıl Çalışıyor?

### 1. Snapshot Alma (Her 10 saniye)
```python
snapshot = {
    'balance': 10530.23,
    'win_rate': 65.5,
    'drawdown_pct': 3.2,
    'portfolio_heat_pct': 5.5,
    'open_positions': 2,
    'positions_detail': [...],
    'recent_trades': [...]
}
```

### 2. Trend Analizi (Son 1 saat)
```python
# Son 360 snapshot'tan trend çıkar
balance_trend = last_balance - first_balance
win_rate_change = last_wr - first_wr
```

### 3. Sorun Tespiti
```python
if drawdown_pct > 15:
    issues.append("❌ Yüksek drawdown")
elif drawdown_pct > 10:
    warnings.append("⚠️  Drawdown yükseliyor")

if win_rate < 40 and trades >= 10:
    issues.append("❌ Düşük win rate")
```

### 4. Sağlık Skoru
```python
health_score = 100
health_score -= len(issues) * 20      # Her sorun -20
health_score -= len(warnings) * 5     # Her uyarı -5

if health_score >= 80: status = "🟢 EXCELLENT"
elif health_score >= 60: status = "🟡 GOOD"
elif health_score >= 40: status = "🟠 WARNING"
else: status = "🔴 CRITICAL"
```

---

## 📊 Neyi İzliyorum?

### Performans Metrikleri:
- ✅ Balance & PnL
- ✅ Win Rate & Profit Factor
- ✅ Sharpe & Sortino Ratios
- ✅ Expectancy
- ✅ MAE / MFE

### Risk Metrikleri:
- ✅ Drawdown (current & max)
- ✅ Portfolio Heat
- ✅ Position Sizes
- ✅ Leverage Usage

### Operasyonel:
- ✅ Trade Frequency
- ✅ Position Duration
- ✅ Entry Quality
- ✅ Exit Timing

### Trend Analizi:
- ✅ Balance trend (10dk, 1h)
- ✅ Win rate değişimi
- ✅ Drawdown trendi
- ✅ Trade frequency

---

## ⚙️ Ayarlar

Monitoring sisteminin ayarları `live_bot_monitor.py` içinde:

```python
self.thresholds = {
    'max_drawdown_pct': 15.0,        # %15 üzeri kritik
    'min_win_rate': 40.0,            # %40 altı sorunlu
    'max_loss_streak': 5,            # 5 ardışık kayıp
    'min_sharpe': 0.5,               # Minimum Sharpe
    'max_portfolio_heat': 12.0,      # %12 max risk
    'max_position_time_hours': 24,   # 24 saat max
}
```

İsterseniz bunları değiştirebilirsiniz.

---

## 🆘 Sorun Giderme

### "Live monitoring not active"
```bash
# live_bot_monitor.py eksik
# Dosyayı ekleyip git push yapın
```

### Snapshot'lar alınmıyor
```python
# Log'larda şunu görmeli:
"🔴 Canlı izleme başlatıldı - Her 10 saniyede snapshot alınıyor"

# Görmüyorsanız:
# 1. Railway logs'u kontrol edin
# 2. ImportError var mı bakın
```

### API 404 veriyor
```bash
# Railway'de botun çalıştığından emin olun
# Railway logs: "-> Server running on port 8080"
```

---

## 📝 Özet

### Sizin İçin:
1. Botu deploy edin
2. Bana "botu incele" deyin
3. Ben size anlık rapor + öneriler sunarım
4. Önerileri uygulayın
5. Tekrar sorun: "Şimdi nasıl?"

### Benim İçin:
1. Her 10 saniyede snapshot alıyorum
2. Trendleri izliyorum
3. Sorunları tespit ediyorum
4. Çözüm önerileri hazırlıyorum
5. Siz sorduğunuzda raporluyorum

---

**Artık botunuz izleniyor! Bana istediğiniz zaman sorun 🔴**
