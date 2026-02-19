"""
🔧 MEVCUT BOTUNUZA ENTEGRASYON REHBERİ
======================================

Bu dosya, trading_bot_improvements.py modülünü mevcut trading_bot_v5.py
dosyanıza nasıl entegre edeceğinizi gösterir.
"""

# ============================================================================
# ADIM 1: MODÜLÜ İMPORT EDİN
# ============================================================================

from trading_bot_improvements import (
    BacktestEngine,
    RiskManager,
    StrategyOptimizer,
    PerformanceMetrics,
    Trade,
    BacktestResult
)

# ============================================================================
# ADIM 2: MEVCUT BOT YAPISINA EKLEYİN
# ============================================================================

class TradingBotV5Enhanced:
    """
    Mevcut trading bot'unuza ekleyeceğiniz iyileştirmeler
    """
    
    def __init__(self):
        # Mevcut bot parametreleri
        self.capital = 10000
        self.max_positions = 7
        self.position_size_pct = 0.09
        
        # YENİ: İyileştirme modülleri
        self.backtest_engine = BacktestEngine(
            initial_capital=self.capital,
            commission_rate=0.0004,  # Binance Futures
            slippage_rate=0.0005
        )
        
        self.risk_manager = RiskManager(
            total_capital=self.capital,
            max_risk_per_trade=0.02,
            max_portfolio_heat=0.10,
            max_correlation=0.7,
            max_drawdown_limit=0.20
        )
        
        self.optimizer = StrategyOptimizer()
        
        # Trade history
        self.all_trades = []
        self.backtest_results = None
    
    # ========================================================================
    # MEVCUT FONKSİYONLARINIZI DEĞİŞTİRİN
    # ========================================================================
    
    def calculate_position_size_OLD(self, price, leverage):
        """ESKİ YÖNTEM - %9 sabit"""
        return self.capital * self.position_size_pct
    
    def calculate_position_size_NEW(self, symbol, entry_price, stop_loss_price, leverage):
        """
        YENİ YÖNTEM - Risk-adjusted position sizing
        
        ÖNEMLİ: Bu fonksiyonu kullanın!
        """
        # Geçmiş performansa göre
        if len(self.all_trades) > 10:
            recent_trades = self.all_trades[-50:]  # Son 50 trade
            winning = [t for t in recent_trades if t.pnl > 0]
            losing = [t for t in recent_trades if t.pnl <= 0]
            
            win_rate = len(winning) / len(recent_trades)
            avg_win = sum(t.pnl for t in winning) / len(winning) if winning else 0
            avg_loss = abs(sum(t.pnl for t in losing) / len(losing)) if losing else 0
            
            # Kelly Criterion ile optimal size
            position = self.risk_manager.calculate_position_size(
                entry_price=entry_price,
                stop_loss_price=stop_loss_price,
                leverage=leverage,
                win_rate=win_rate,
                avg_win=avg_win,
                avg_loss=avg_loss
            )
        else:
            # Yeterli veri yoksa fixed risk
            position = self.risk_manager.calculate_position_size(
                entry_price=entry_price,
                stop_loss_price=stop_loss_price,
                leverage=leverage
            )
        
        # Portfolio heat check
        if self.risk_manager.calculate_portfolio_heat() > 0.08:
            # Çok riskli, trade açma
            return None
        
        # Drawdown protection
        should_stop, reason = self.risk_manager.should_stop_trading()
        if should_stop:
            print(f"⚠️  Trading durduruldu: {reason}")
            return None
        
        return position
    
    def open_position(self, symbol, entry_price, direction, leverage, stop_loss, take_profit):
        """
        YENİ: Risk-aware position açma
        """
        # Position size hesapla
        position = self.calculate_position_size_NEW(
            symbol, entry_price, stop_loss, leverage
        )
        
        if position is None:
            print(f"❌ {symbol}: Risk limiti aşıldı, trade açılmadı")
            return False
        
        # Correlation check (eğer başka pozisyonlar varsa)
        # correlation_matrix = self.calculate_correlation_matrix()  # Kendi implementasyonunuz
        # if not self.risk_manager.check_correlation(symbol, correlation_matrix):
        #     print(f"❌ {symbol}: Çok yüksek correlation, trade açılmadı")
        #     return False
        
        # Position'ı aç
        size_usd = position['size_usd']
        
        # Risk manager'a bildir
        self.risk_manager.add_position(
            symbol=symbol,
            size=size_usd,
            entry_price=entry_price,
            stop_loss=stop_loss,
            leverage=leverage
        )
        
        print(f"✅ {symbol}: Position açıldı")
        print(f"   Size: ${size_usd:,.2f} ({position['size_pct']:.1f}%)")
        print(f"   Risk: ${position['risk_amount']:.2f}")
        print(f"   Method: {position['method']}")
        
        return True
    
    def close_position(self, symbol, exit_price, entry_time, entry_price, size, leverage, stop_loss, take_profit):
        """
        YENİ: Trade'i kapat ve kaydet
        """
        from datetime import datetime
        
        # PnL hesapla
        price_change = (exit_price - entry_price) / entry_price
        pnl = size * price_change * leverage
        pnl_pct = (pnl / size) * 100
        
        # Commission ve slippage
        commission = size * leverage * 0.0004 * 2
        slippage = size * 0.0005
        net_pnl = pnl - commission - slippage
        
        # Trade objesi oluştur
        trade = Trade(
            entry_time=entry_time,
            exit_time=datetime.now(),
            symbol=symbol,
            direction='LONG',  # veya 'SHORT'
            entry_price=entry_price,
            exit_price=exit_price,
            size=size,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit,
            pnl=net_pnl,
            pnl_pct=pnl_pct,
            commission=commission,
            slippage=slippage,
            exit_reason='TP' if exit_price >= take_profit else 'SL' if exit_price <= stop_loss else 'SIGNAL'
        )
        
        # Kaydet
        self.all_trades.append(trade)
        
        # Risk manager'dan kaldır
        self.risk_manager.remove_position(symbol)
        
        # Sermaye güncelle
        self.capital += net_pnl
        self.risk_manager.total_capital = self.capital
        self.risk_manager.update_drawdown(self.capital)
        
        # Performance güncelle
        if len(self.all_trades) % 10 == 0:  # Her 10 trade'de bir
            self.update_performance_metrics()
        
        return trade
    
    def update_performance_metrics(self):
        """
        Her 10 trade'de bir performans metriklerini güncelle
        """
        if len(self.all_trades) < 10:
            return
        
        metrics = PerformanceMetrics(self.all_trades)
        
        # Sharpe ratio
        sharpe = metrics.sharpe_ratio()
        
        # Expectancy
        exp = metrics.expectancy()
        
        # Streaks
        streaks = metrics.calculate_streaks()
        
        # Risk-adjusted metrics
        total_return_pct = ((self.capital - 10000) / 10000) * 100
        max_dd_pct = self.risk_manager.current_drawdown * 100
        risk_adj = metrics.risk_adjusted_metrics(total_return_pct, max_dd_pct)
        
        print("\n" + "="*70)
        print("📊 PERFORMANS GÜNCELLEMESİ")
        print("="*70)
        print(f"Toplam Trade:          {len(self.all_trades)}")
        print(f"Sermaye:               ${self.capital:,.2f}")
        print(f"Sharpe Ratio:          {sharpe:.2f}")
        print(f"Expectancy:            ${exp['expectancy']:.2f}")
        print(f"Current Streak:        {streaks['current_streak']:+d}")
        print(f"Performance Grade:     {risk_adj['grade']}")
        print(f"Portfolio Heat:        {self.risk_manager.calculate_portfolio_heat():.1%}")
        print(f"Current Drawdown:      {self.risk_manager.current_drawdown:.1%}")
        print("="*70 + "\n")
    
    def run_backtest_on_strategy(self, signals, price_data):
        """
        Yeni bir stratejiyi backtest ile test et
        """
        print("🔄 Backtest başlatılıyor...")
        
        result = self.backtest_engine.run_backtest(signals, price_data)
        
        self.backtest_results = result
        
        print(f"\n✅ Backtest tamamlandı!")
        print(f"   Win Rate: {result.win_rate:.1f}%")
        print(f"   Return: {result.total_return_pct:+.2f}%")
        print(f"   Sharpe: {result.sharpe_ratio:.2f}")
        print(f"   Max DD: {result.max_drawdown_pct:.2f}%")
        
        # Overfitting check
        # (In-sample ve out-sample'ı kendiniz ayırın)
        return result
    
    def detect_strategy_overfitting(self, in_sample_result, out_sample_result):
        """
        Strateji overfit mi?
        """
        overfit = self.optimizer.detect_overfitting(
            in_sample_sharpe=in_sample_result.sharpe_ratio,
            out_sample_sharpe=out_sample_result.sharpe_ratio,
            in_sample_trades=in_sample_result.total_trades,
            out_sample_trades=out_sample_result.total_trades
        )
        
        print("\n" + "="*70)
        print("🔍 OVERFITTING ANALİZİ")
        print("="*70)
        print(f"Risk Level:            {overfit['risk_level']}")
        print(f"Overfit Score:         {overfit['overfit_score']}/10")
        print(f"Is Overfit:            {'⚠️  EVET' if overfit['is_overfit'] else '✅ HAYIR'}")
        print(f"Öneri:                 {overfit['recommendation']}")
        print("="*70 + "\n")
        
        return overfit
    
    def run_monte_carlo_risk_analysis(self):
        """
        Monte Carlo ile risk analizi
        """
        if len(self.all_trades) < 20:
            print("❌ Monte Carlo için en az 20 trade gerekli")
            return None
        
        print("🎲 Monte Carlo simülasyonu başlatılıyor...")
        
        mc_result = self.optimizer.monte_carlo_simulation(
            self.all_trades,
            num_simulations=1000
        )
        
        print(f"\n✅ 1000 simülasyon tamamlandı")
        print(f"   Ortalama Return:      {mc_result['return_mean']:.2f}%")
        print(f"   5. Percentile (Worst): {mc_result['return_5th_percentile']:.2f}%")
        print(f"   95. Percentile (Best): {mc_result['return_95th_percentile']:.2f}%")
        print(f"   Pozitif Olasılık:     {mc_result['probability_positive']:.1%}")
        print(f"   Worst Case DD:        {mc_result['drawdown_95th_percentile']:.2f}%")
        
        return mc_result
    
    def generate_full_report(self):
        """
        Tam performans raporu
        """
        if not self.all_trades:
            print("❌ Henüz trade yok")
            return
        
        # BacktestResult objesi oluştur (mevcut trades'den)
        from datetime import datetime, timedelta
        
        # Basitleştirilmiş backtest result
        winning = [t for t in self.all_trades if t.pnl > 0]
        losing = [t for t in self.all_trades if t.pnl <= 0]
        
        total_return = self.capital - 10000
        total_return_pct = (total_return / 10000) * 100
        
        profit_factor = sum(t.pnl for t in winning) / abs(sum(t.pnl for t in losing)) if losing else 0
        
        # Equity curve
        equity_curve = [10000]
        running_capital = 10000
        for trade in self.all_trades:
            running_capital += trade.pnl
            equity_curve.append(running_capital)
        
        # Drawdown curve
        peak = 10000
        drawdown_curve = [0]
        for capital in equity_curve[1:]:
            if capital > peak:
                peak = capital
            dd = (peak - capital) / peak
            drawdown_curve.append(dd)
        
        max_dd = max(drawdown_curve)
        
        result = BacktestResult(
            trades=self.all_trades,
            initial_capital=10000,
            final_capital=self.capital,
            total_return=total_return,
            total_return_pct=total_return_pct,
            total_trades=len(self.all_trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=(len(winning) / len(self.all_trades)) * 100,
            profit_factor=profit_factor,
            sharpe_ratio=PerformanceMetrics(self.all_trades).sharpe_ratio(),
            sortino_ratio=PerformanceMetrics(self.all_trades).sortino_ratio(),
            calmar_ratio=total_return_pct / (max_dd * 100) if max_dd > 0 else 0,
            max_drawdown=max_dd * 10000,
            max_drawdown_pct=max_dd * 100,
            avg_win=sum(t.pnl for t in winning) / len(winning) if winning else 0,
            avg_loss=sum(t.pnl for t in losing) / len(losing) if losing else 0,
            largest_win=max([t.pnl for t in winning]) if winning else 0,
            largest_loss=min([t.pnl for t in losing]) if losing else 0,
            avg_trade_duration=timedelta(seconds=sum([(t.exit_time - t.entry_time).total_seconds() for t in self.all_trades]) / len(self.all_trades)),
            total_commission=sum(t.commission for t in self.all_trades),
            total_slippage=sum(t.slippage for t in self.all_trades),
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve
        )
        
        # Rapor oluştur
        metrics = PerformanceMetrics(self.all_trades)
        report = metrics.generate_report(result)
        
        print(report)
        
        return result


# ============================================================================
# ADIM 3: MEVCUT BOTUNUZU DEĞİŞTİRİN
# ============================================================================

"""
MEVCUT trading_bot_v5.py dosyanızda şunları yapın:

1. En üste import ekleyin:
   from trading_bot_improvements import BacktestEngine, RiskManager, StrategyOptimizer, PerformanceMetrics

2. __init__ metodunda modülleri initialize edin:
   self.risk_manager = RiskManager(total_capital=self.capital)
   self.backtest_engine = BacktestEngine(initial_capital=self.capital)

3. calculate_position_size fonksiyonunu değiştirin:
   - Eski %9 sabit yerine
   - risk_manager.calculate_position_size() kullanın

4. Trade kapanışında:
   - Trade objesi oluşturun
   - self.all_trades.append(trade)
   - risk_manager.update_drawdown(capital)

5. Her 10 trade'de bir:
   - self.update_performance_metrics() çağırın

6. Web endpoint'e ekleyin:
   GET /api/performance-report -> generate_full_report()
   GET /api/monte-carlo -> run_monte_carlo_risk_analysis()
"""


# ============================================================================
# ADIM 4: WEB ARAYÜZÜNE EKLEYIN
# ============================================================================

"""
HTML/JavaScript tarafında:

1. Yeni bir panel ekleyin "Risk Yönetimi":
   - Current portfolio heat
   - Current drawdown
   - Open positions risk

2. "Performans" paneline ekleyin:
   - Sharpe ratio (realtime)
   - Expectancy
   - Current streak
   - Performance grade

3. Yeni bir buton: "Detaylı Rapor"
   - fetch('/api/performance-report')
   - Modal'da göster

4. Yeni bir buton: "Monte Carlo Analizi"
   - fetch('/api/monte-carlo')
   - Grafik ile göster
"""


# ============================================================================
# ÖRNEK ENTEGRASYON KOD PARÇALARI
# ============================================================================

def example_integration():
    """
    Gerçek botunuzda nasıl kullanacağınız
    """
    
    # Bot oluştur
    bot = TradingBotV5Enhanced()
    
    # 1. Position aç (eski yöntem yerine)
    from datetime import datetime
    
    symbol = "BTCUSDT"
    entry_price = 50000
    leverage = 3
    stop_loss = 49000  # %2 risk
    take_profit = 51000  # %2 profit
    
    # Risk-aware position açma
    success = bot.open_position(
        symbol=symbol,
        entry_price=entry_price,
        direction='LONG',
        leverage=leverage,
        stop_loss=stop_loss,
        take_profit=take_profit
    )
    
    if success:
        print("✅ Position açıldı")
    else:
        print("❌ Risk limiti nedeniyle position açılamadı")
    
    # 2. Position kapat
    exit_price = 50500
    trade = bot.close_position(
        symbol=symbol,
        exit_price=exit_price,
        entry_time=datetime.now(),
        entry_price=entry_price,
        size=3000,
        leverage=leverage,
        stop_loss=stop_loss,
        take_profit=take_profit
    )
    
    print(f"Trade kapatıldı: PnL = ${trade.pnl:.2f}")
    
    # 3. Periyodik olarak rapor
    if len(bot.all_trades) >= 10:
        bot.generate_full_report()
    
    # 4. Monte Carlo risk analizi
    if len(bot.all_trades) >= 20:
        bot.run_monte_carlo_risk_analysis()


if __name__ == '__main__':
    example_integration()
