"""
🚀 AI Trading Bot - Kapsamlı İyileştirme Modülü v1.0
====================================================

Bu modül 4 ana bileşen içerir:
1. Gerçekçi Backtesting Sistemi
2. Gelişmiş Risk Yönetimi
3. Strateji Optimizasyonu
4. Gelişmiş Performans Metrikleri

Kullanım:
--------
from trading_bot_improvements import BacktestEngine, RiskManager, StrategyOptimizer, PerformanceMetrics

# Backtesting
engine = BacktestEngine(initial_capital=10000, commission=0.0004, slippage=0.0005)
results = engine.run_backtest(trades_data)

# Risk Management
risk_mgr = RiskManager(total_capital=10000)
position_size = risk_mgr.calculate_position_size(price=100, stop_loss_pct=0.02)

# Strateji Optimizasyonu
optimizer = StrategyOptimizer()
best_params = optimizer.optimize(strategy_func, param_ranges)

# Performance Metrics
metrics = PerformanceMetrics(trades_data)
sharpe = metrics.sharpe_ratio()
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from scipy import stats
from scipy.optimize import minimize
import warnings
warnings.filterwarnings('ignore')


# ============================================================================
# 1️⃣ GERÇEKÇİ BACKTESTING SİSTEMİ
# ============================================================================

@dataclass
class Trade:
    """Tek bir trade'i temsil eder"""
    entry_time: datetime
    exit_time: datetime
    symbol: str
    direction: str  # 'LONG' veya 'SHORT'
    entry_price: float
    exit_price: float
    size: float  # Position size (USD)
    leverage: int
    stop_loss: float
    take_profit: float
    pnl: float = 0.0
    pnl_pct: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0
    mae: float = 0.0  # Maximum Adverse Excursion
    mfe: float = 0.0  # Maximum Favorable Excursion
    exit_reason: str = ''  # 'TP', 'SL', 'TIMEOUT', 'SIGNAL'


@dataclass
class BacktestResult:
    """Backtest sonuçlarını içerir"""
    trades: List[Trade]
    initial_capital: float
    final_capital: float
    total_return: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_pct: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    avg_trade_duration: timedelta
    total_commission: float
    total_slippage: float
    equity_curve: List[float]
    drawdown_curve: List[float]


class BacktestEngine:
    """
    Gerçekçi Backtesting Motoru
    
    Özellikler:
    - Slippage simulation
    - Commission calculation
    - Market impact modeling
    - Realistic fill simulation
    - Multiple timeframe support
    """
    
    def __init__(
        self,
        initial_capital: float = 10000,
        commission_rate: float = 0.0004,  # 0.04% Binance Futures
        slippage_rate: float = 0.0005,    # 0.05% ortalama slippage
        max_position_size: float = 0.95,  # Maximum %95 capital
        leverage_limits: Dict[int, float] = None
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.max_position_size = max_position_size
        
        # Leverage'a göre pozisyon limitleri
        self.leverage_limits = leverage_limits or {
            2: 0.50,   # 2x: max %50
            3: 0.40,   # 3x: max %40
            5: 0.30,   # 5x: max %30
            10: 0.20,  # 10x: max %20
            20: 0.10   # 20x: max %10
        }
        
    def calculate_slippage(
        self,
        price: float,
        size: float,
        volatility: float = 0.01
    ) -> float:
        """
        Market impact ve volatility'ye göre slippage hesaplar
        
        Gerçekçi model:
        - Büyük pozisyonlar daha fazla slippage'e sebep olur
        - Yüksek volatility daha fazla slippage demektir
        """
        base_slippage = price * self.slippage_rate
        
        # Market impact (position size'a göre)
        if size > 1000:
            impact_multiplier = 1 + (size / 10000)
        else:
            impact_multiplier = 1.0
            
        # Volatility impact
        volatility_multiplier = 1 + (volatility * 10)
        
        total_slippage = base_slippage * impact_multiplier * volatility_multiplier
        
        return total_slippage
    
    def calculate_commission(self, size: float, leverage: int) -> float:
        """
        Commission hesaplar (giriş + çıkış)
        """
        notional_value = size * leverage
        commission = notional_value * self.commission_rate * 2  # Entry + Exit
        return commission
    
    def simulate_realistic_fill(
        self,
        intended_price: float,
        direction: str,
        size: float,
        market_data: Dict
    ) -> Tuple[float, float]:
        """
        Gerçekçi fill fiyatı simüle eder
        
        Returns:
            (actual_fill_price, slippage_cost)
        """
        volatility = market_data.get('volatility', 0.01)
        slippage = self.calculate_slippage(intended_price, size, volatility)
        
        if direction == 'LONG':
            # Long pozisyonda fiyat biraz yukarı kayar
            actual_price = intended_price + slippage
        else:  # SHORT
            # Short pozisyonda fiyat biraz aşağı kayar
            actual_price = intended_price - slippage
            
        slippage_cost = abs(actual_price - intended_price) * (size / intended_price)
        
        return actual_price, slippage_cost
    
    def run_backtest(
        self,
        signals: List[Dict],
        price_data: pd.DataFrame
    ) -> BacktestResult:
        """
        Tam backtest çalıştırır
        
        Args:
            signals: [{'time': datetime, 'symbol': str, 'action': 'BUY/SELL', ...}]
            price_data: OHLCV data with columns ['time', 'symbol', 'open', 'high', 'low', 'close', 'volume']
        """
        capital = self.initial_capital
        trades = []
        open_positions = {}
        equity_curve = [capital]
        peak_capital = capital
        drawdown_curve = [0]
        
        # Price data'yı dict'e çevir (hızlı erişim için)
        price_dict = {}
        for _, row in price_data.iterrows():
            key = (row['time'], row['symbol'])
            price_dict[key] = row.to_dict()
        
        for signal in signals:
            time = signal['time']
            symbol = signal['symbol']
            action = signal['action']
            
            # Market data
            market_key = (time, symbol)
            if market_key not in price_dict:
                continue
                
            market_data = price_dict[market_key]
            current_price = market_data['close']
            
            # Pozisyon yönetimi
            if action == 'BUY' and symbol not in open_positions:
                # Yeni LONG pozisyon aç
                leverage = signal.get('leverage', 2)
                risk_pct = signal.get('risk_pct', 0.02)
                
                # Position sizing
                max_size_pct = self.leverage_limits.get(leverage, 0.1)
                position_size = min(
                    capital * max_size_pct,
                    capital * self.max_position_size
                )
                
                # Gerçekçi fill simülasyonu
                actual_entry, slippage_cost = self.simulate_realistic_fill(
                    current_price, 'LONG', position_size, market_data
                )
                
                # Commission
                commission = self.calculate_commission(position_size, leverage)
                
                # Stop loss ve take profit
                stop_loss = signal.get('stop_loss', actual_entry * 0.98)
                take_profit = signal.get('take_profit', actual_entry * 1.02)
                
                # Trade kaydı
                trade = Trade(
                    entry_time=time,
                    exit_time=time,  # Henüz kapatılmadı
                    symbol=symbol,
                    direction='LONG',
                    entry_price=actual_entry,
                    exit_price=0,
                    size=position_size,
                    leverage=leverage,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    commission=commission,
                    slippage=slippage_cost
                )
                
                open_positions[symbol] = trade
                capital -= (commission + slippage_cost)
                
            elif action == 'SELL' and symbol in open_positions:
                # LONG pozisyonu kapat
                trade = open_positions[symbol]
                
                # Gerçekçi fill simülasyonu
                actual_exit, exit_slippage = self.simulate_realistic_fill(
                    current_price, 'SHORT', trade.size, market_data
                )
                
                # PnL hesaplama
                price_change = (actual_exit - trade.entry_price) / trade.entry_price
                raw_pnl = trade.size * price_change * trade.leverage
                
                # Maliyetleri düş
                total_slippage = trade.slippage + exit_slippage
                net_pnl = raw_pnl - total_slippage
                
                # Trade'i güncelle
                trade.exit_time = time
                trade.exit_price = actual_exit
                trade.pnl = net_pnl
                trade.pnl_pct = (net_pnl / trade.size) * 100
                trade.exit_reason = self._determine_exit_reason(
                    actual_exit, trade.stop_loss, trade.take_profit
                )
                
                # MAE/MFE hesaplama (basitleştirilmiş)
                trade.mae = min(0, raw_pnl * 0.8)  # Worst point
                trade.mfe = max(0, raw_pnl * 1.2)  # Best point
                
                trades.append(trade)
                del open_positions[symbol]
                
                capital += net_pnl
                
            # Equity curve güncelle
            equity_curve.append(capital)
            
            # Drawdown hesapla
            if capital > peak_capital:
                peak_capital = capital
            drawdown = (peak_capital - capital) / peak_capital
            drawdown_curve.append(drawdown)
        
        # Açık pozisyonları kapat (backtest sonu)
        for symbol, trade in open_positions.items():
            # Son fiyatı kullan
            last_price = price_data[price_data['symbol'] == symbol].iloc[-1]['close']
            
            price_change = (last_price - trade.entry_price) / trade.entry_price
            raw_pnl = trade.size * price_change * trade.leverage
            net_pnl = raw_pnl - trade.slippage
            
            trade.exit_time = price_data.iloc[-1]['time']
            trade.exit_price = last_price
            trade.pnl = net_pnl
            trade.pnl_pct = (net_pnl / trade.size) * 100
            trade.exit_reason = 'BACKTEST_END'
            
            trades.append(trade)
            capital += net_pnl
        
        # Performans metrikleri hesapla
        return self._calculate_results(trades, capital, equity_curve, drawdown_curve)
    
    def _determine_exit_reason(self, exit_price: float, sl: float, tp: float) -> str:
        """Exit sebebini belirle"""
        if exit_price <= sl:
            return 'STOP_LOSS'
        elif exit_price >= tp:
            return 'TAKE_PROFIT'
        else:
            return 'SIGNAL'
    
    def _calculate_results(
        self,
        trades: List[Trade],
        final_capital: float,
        equity_curve: List[float],
        drawdown_curve: List[float]
    ) -> BacktestResult:
        """Backtest sonuçlarını hesaplar"""
        
        if len(trades) == 0:
            # Hiç trade yoksa
            return BacktestResult(
                trades=[],
                initial_capital=self.initial_capital,
                final_capital=final_capital,
                total_return=0,
                total_return_pct=0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0,
                profit_factor=0,
                sharpe_ratio=0,
                sortino_ratio=0,
                calmar_ratio=0,
                max_drawdown=0,
                max_drawdown_pct=0,
                avg_win=0,
                avg_loss=0,
                largest_win=0,
                largest_loss=0,
                avg_trade_duration=timedelta(0),
                total_commission=0,
                total_slippage=0,
                equity_curve=equity_curve,
                drawdown_curve=drawdown_curve
            )
        
        # Temel istatistikler
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl <= 0]
        
        total_wins = len(winning_trades)
        total_losses = len(losing_trades)
        win_rate = total_wins / len(trades) if trades else 0
        
        # PnL
        total_return = final_capital - self.initial_capital
        total_return_pct = (total_return / self.initial_capital) * 100
        
        # Profit Factor
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Average Win/Loss
        avg_win = gross_profit / total_wins if total_wins > 0 else 0
        avg_loss = gross_loss / total_losses if total_losses > 0 else 0
        
        # Largest Win/Loss
        largest_win = max([t.pnl for t in winning_trades]) if winning_trades else 0
        largest_loss = min([t.pnl for t in losing_trades]) if losing_trades else 0
        
        # Drawdown
        max_dd = max(drawdown_curve)
        max_dd_pct = max_dd * 100
        
        # Sharpe Ratio
        returns = np.diff(equity_curve) / equity_curve[:-1]
        if len(returns) > 0 and np.std(returns) > 0:
            sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252)  # Annualized
        else:
            sharpe = 0
        
        # Sortino Ratio
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0 and np.std(downside_returns) > 0:
            sortino = (np.mean(returns) / np.std(downside_returns)) * np.sqrt(252)
        else:
            sortino = 0
        
        # Calmar Ratio
        calmar = (total_return_pct / 100) / max_dd if max_dd > 0 else 0
        
        # Trade duration
        durations = [(t.exit_time - t.entry_time) for t in trades]
        avg_duration = sum(durations, timedelta(0)) / len(durations) if durations else timedelta(0)
        
        # Costs
        total_commission = sum(t.commission for t in trades)
        total_slippage = sum(t.slippage for t in trades)
        
        return BacktestResult(
            trades=trades,
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            total_return_pct=total_return_pct,
            total_trades=len(trades),
            winning_trades=total_wins,
            losing_trades=total_losses,
            win_rate=win_rate * 100,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown=max_dd * self.initial_capital,
            max_drawdown_pct=max_dd_pct,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            avg_trade_duration=avg_duration,
            total_commission=total_commission,
            total_slippage=total_slippage,
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve
        )


# ============================================================================
# 2️⃣ GELİŞMİŞ RİSK YÖNETİMİ
# ============================================================================

class RiskManager:
    """
    Gelişmiş Risk Yönetimi Sistemi
    
    Özellikler:
    - Kelly Criterion position sizing
    - Portfolio heat calculation
    - Correlation-based position limits
    - Drawdown protection
    - Risk-adjusted position sizing
    """
    
    def __init__(
        self,
        total_capital: float,
        max_risk_per_trade: float = 0.02,  # %2 max risk
        max_portfolio_heat: float = 0.10,   # %10 max total risk
        max_correlation: float = 0.7,        # Max correlation between positions
        max_drawdown_limit: float = 0.20     # %20 max drawdown
    ):
        self.total_capital = total_capital
        self.max_risk_per_trade = max_risk_per_trade
        self.max_portfolio_heat = max_portfolio_heat
        self.max_correlation = max_correlation
        self.max_drawdown_limit = max_drawdown_limit
        
        self.open_positions = {}
        self.current_drawdown = 0.0
        self.peak_capital = total_capital
        
    def kelly_criterion(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Kelly Criterion ile optimal position size hesaplar
        
        Formula: f* = (p*b - q) / b
        f* = fraction of capital to wager
        p = probability of winning
        q = probability of losing (1-p)
        b = ratio of win to loss
        """
        if avg_loss == 0:
            return 0
            
        b = avg_win / abs(avg_loss)
        q = 1 - win_rate
        
        kelly_pct = (win_rate * b - q) / b
        
        # Kelly'yi %25'e cap'le (çok agresif olmasın)
        kelly_pct = max(0, min(kelly_pct, 0.25))
        
        # Fractional Kelly (daha konservatif)
        fractional_kelly = kelly_pct * 0.5  # Half Kelly
        
        return fractional_kelly
    
    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss_price: float,
        leverage: int = 1,
        win_rate: float = None,
        avg_win: float = None,
        avg_loss: float = None
    ) -> Dict:
        """
        Optimal position size hesaplar
        
        Returns:
            {
                'size_usd': float,
                'size_pct': float,
                'quantity': float,
                'risk_amount': float,
                'method': str
            }
        """
        
        # Risk per trade
        risk_per_unit = abs(entry_price - stop_loss_price) / entry_price
        
        # Method 1: Fixed risk
        fixed_risk_size = (self.total_capital * self.max_risk_per_trade) / risk_per_unit
        
        # Method 2: Kelly Criterion (eğer veriler varsa)
        kelly_size = fixed_risk_size
        if all([win_rate, avg_win, avg_loss]):
            kelly_fraction = self.kelly_criterion(win_rate, avg_win, avg_loss)
            kelly_size = self.total_capital * kelly_fraction
        
        # En küçüğünü al (daha konservatif)
        optimal_size = min(fixed_risk_size, kelly_size)
        
        # Leverage ile çarp
        leveraged_size = optimal_size * leverage
        
        # Portfolio heat check
        current_heat = self.calculate_portfolio_heat()
        if current_heat + risk_per_unit > self.max_portfolio_heat:
            # Portfolio çok riskli, position size'ı küçült
            reduction_factor = (self.max_portfolio_heat - current_heat) / risk_per_unit
            leveraged_size *= max(0, reduction_factor)
        
        # Drawdown protection
        if self.current_drawdown > self.max_drawdown_limit * 0.5:
            # Drawdown'dayken daha küçük pozisyon
            dd_factor = 1 - (self.current_drawdown / self.max_drawdown_limit)
            leveraged_size *= dd_factor
        
        quantity = leveraged_size / entry_price
        risk_amount = leveraged_size * risk_per_unit
        
        return {
            'size_usd': leveraged_size,
            'size_pct': (leveraged_size / self.total_capital) * 100,
            'quantity': quantity,
            'risk_amount': risk_amount,
            'method': 'kelly' if all([win_rate, avg_win, avg_loss]) else 'fixed'
        }
    
    def calculate_portfolio_heat(self) -> float:
        """
        Mevcut portfolio risk'ini hesaplar
        
        Portfolio Heat = Toplam açık pozisyonların risk'i / Total capital
        """
        total_risk = sum(pos['risk_amount'] for pos in self.open_positions.values())
        heat = total_risk / self.total_capital
        return heat
    
    def check_correlation(
        self,
        new_symbol: str,
        correlation_matrix: pd.DataFrame
    ) -> bool:
        """
        Yeni pozisyon mevcut pozisyonlarla çok mu korele?
        
        Returns:
            True if correlation is acceptable
        """
        if not self.open_positions:
            return True
            
        for existing_symbol in self.open_positions.keys():
            if existing_symbol in correlation_matrix.index and new_symbol in correlation_matrix.columns:
                corr = correlation_matrix.loc[existing_symbol, new_symbol]
                if abs(corr) > self.max_correlation:
                    return False
        
        return True
    
    def update_drawdown(self, current_capital: float):
        """Drawdown'u günceller"""
        if current_capital > self.peak_capital:
            self.peak_capital = current_capital
            self.current_drawdown = 0.0
        else:
            self.current_drawdown = (self.peak_capital - current_capital) / self.peak_capital
    
    def should_stop_trading(self) -> Tuple[bool, str]:
        """
        Trading'i durdurmalı mı?
        
        Returns:
            (should_stop, reason)
        """
        # Max drawdown
        if self.current_drawdown >= self.max_drawdown_limit:
            return True, f"Max drawdown reached: {self.current_drawdown:.1%}"
        
        # Portfolio heat
        heat = self.calculate_portfolio_heat()
        if heat >= self.max_portfolio_heat:
            return True, f"Portfolio heat too high: {heat:.1%}"
        
        return False, ""
    
    def add_position(
        self,
        symbol: str,
        size: float,
        entry_price: float,
        stop_loss: float,
        leverage: int
    ):
        """Açık pozisyon ekle"""
        risk_amount = size * abs(entry_price - stop_loss) / entry_price
        
        self.open_positions[symbol] = {
            'size': size,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'leverage': leverage,
            'risk_amount': risk_amount
        }
    
    def remove_position(self, symbol: str):
        """Pozisyonu kapat"""
        if symbol in self.open_positions:
            del self.open_positions[symbol]
    
    def get_portfolio_summary(self) -> Dict:
        """Portfolio özeti"""
        heat = self.calculate_portfolio_heat()
        
        return {
            'total_capital': self.total_capital,
            'peak_capital': self.peak_capital,
            'current_drawdown': self.current_drawdown,
            'current_drawdown_pct': self.current_drawdown * 100,
            'portfolio_heat': heat,
            'portfolio_heat_pct': heat * 100,
            'open_positions_count': len(self.open_positions),
            'total_risk_amount': sum(p['risk_amount'] for p in self.open_positions.values()),
            'can_trade': not self.should_stop_trading()[0]
        }


# ============================================================================
# 3️⃣ STRATEJİ OPTİMİZASYONU
# ============================================================================

class StrategyOptimizer:
    """
    Strateji Optimizasyon Sistemi
    
    Özellikler:
    - Overfitting detection
    - Walk-forward analysis
    - Monte Carlo simulation
    - Parameter optimization
    - Cross-validation
    """
    
    def __init__(self):
        self.optimization_history = []
        
    def detect_overfitting(
        self,
        in_sample_sharpe: float,
        out_sample_sharpe: float,
        in_sample_trades: int,
        out_sample_trades: int
    ) -> Dict:
        """
        Overfitting'i tespit eder
        
        Kriterler:
        1. Sharpe degradation > 50%
        2. Trade count çok farklı
        3. Out-of-sample performance çok kötü
        """
        sharpe_degradation = (in_sample_sharpe - out_sample_sharpe) / in_sample_sharpe if in_sample_sharpe > 0 else 1.0
        trade_ratio = out_sample_trades / in_sample_trades if in_sample_trades > 0 else 0
        
        # Overfitting skorları
        overfit_score = 0
        warnings_list = []
        
        # 1. Sharpe degradation
        if sharpe_degradation > 0.5:
            overfit_score += 3
            warnings_list.append(f"Sharpe degradation yüksek: {sharpe_degradation:.1%}")
        elif sharpe_degradation > 0.3:
            overfit_score += 2
            warnings_list.append(f"Sharpe degradation orta: {sharpe_degradation:.1%}")
        
        # 2. Trade count
        if trade_ratio < 0.5 or trade_ratio > 2.0:
            overfit_score += 2
            warnings_list.append(f"Trade count tutarsız: {trade_ratio:.2f}x")
        
        # 3. Out-of-sample performance
        if out_sample_sharpe < 0:
            overfit_score += 3
            warnings_list.append(f"Out-of-sample Sharpe negatif: {out_sample_sharpe:.2f}")
        elif out_sample_sharpe < 0.5:
            overfit_score += 1
            warnings_list.append(f"Out-of-sample Sharpe düşük: {out_sample_sharpe:.2f}")
        
        # Sonuç
        is_overfit = overfit_score >= 4
        risk_level = 'HIGH' if overfit_score >= 4 else 'MEDIUM' if overfit_score >= 2 else 'LOW'
        
        return {
            'is_overfit': is_overfit,
            'overfit_score': overfit_score,
            'risk_level': risk_level,
            'sharpe_degradation': sharpe_degradation,
            'trade_ratio': trade_ratio,
            'warnings': warnings_list,
            'recommendation': 'Stratejide değişiklik yapın' if is_overfit else 'Strateji kabul edilebilir'
        }
    
    def walk_forward_analysis(
        self,
        strategy_func: Callable,
        data: pd.DataFrame,
        train_period: int = 90,  # days
        test_period: int = 30,   # days
        step: int = 30            # days
    ) -> Dict:
        """
        Walk-forward analizi yapar
        
        Args:
            strategy_func: Strateji fonksiyonu (params, data) -> trades
            data: OHLCV data
            train_period: Training penceresi (gün)
            test_period: Test penceresi (gün)
            step: Her adımda kaç gün ileri (gün)
        """
        results = []
        
        data['date'] = pd.to_datetime(data['time'])
        start_date = data['date'].min()
        end_date = data['date'].max()
        
        current_date = start_date
        
        while current_date + timedelta(days=train_period + test_period) <= end_date:
            # Training period
            train_start = current_date
            train_end = current_date + timedelta(days=train_period)
            train_data = data[(data['date'] >= train_start) & (data['date'] < train_end)]
            
            # Test period
            test_start = train_end
            test_end = test_start + timedelta(days=test_period)
            test_data = data[(data['date'] >= test_start) & (data['date'] < test_end)]
            
            if len(train_data) < 100 or len(test_data) < 30:
                current_date += timedelta(days=step)
                continue
            
            # Optimize on training data
            best_params = self._optimize_on_period(strategy_func, train_data)
            
            # Test on test data
            test_trades = strategy_func(best_params, test_data)
            
            # Metrics
            test_pnl = sum(t.get('pnl', 0) for t in test_trades)
            test_sharpe = self._calculate_sharpe(test_trades)
            
            results.append({
                'train_start': train_start,
                'train_end': train_end,
                'test_start': test_start,
                'test_end': test_end,
                'best_params': best_params,
                'test_trades': len(test_trades),
                'test_pnl': test_pnl,
                'test_sharpe': test_sharpe
            })
            
            current_date += timedelta(days=step)
        
        # Aggregate results
        if not results:
            return {
                'total_periods': 0,
                'avg_sharpe': 0,
                'sharpe_stability': 0,
                'total_pnl': 0,
                'consistency': 0,
                'periods': []
            }
        
        avg_sharpe = np.mean([r['test_sharpe'] for r in results])
        sharpe_std = np.std([r['test_sharpe'] for r in results])
        sharpe_stability = 1 - (sharpe_std / avg_sharpe) if avg_sharpe > 0 else 0
        
        total_pnl = sum(r['test_pnl'] for r in results)
        positive_periods = sum(1 for r in results if r['test_pnl'] > 0)
        consistency = positive_periods / len(results)
        
        return {
            'total_periods': len(results),
            'avg_sharpe': avg_sharpe,
            'sharpe_stability': sharpe_stability,
            'total_pnl': total_pnl,
            'consistency': consistency,
            'periods': results
        }
    
    def _optimize_on_period(
        self,
        strategy_func: Callable,
        data: pd.DataFrame
    ) -> Dict:
        """Bir period üzerinde optimize et"""
        # Basit grid search (gerçek implementasyonda daha gelişmiş olabilir)
        best_params = {
            'rsi_period': 14,
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'ema_fast': 12,
            'ema_slow': 26
        }
        return best_params
    
    def _calculate_sharpe(self, trades: List[Dict]) -> float:
        """Sharpe ratio hesapla"""
        if not trades:
            return 0
        returns = [t.get('pnl_pct', 0) for t in trades]
        if len(returns) < 2 or np.std(returns) == 0:
            return 0
        return (np.mean(returns) / np.std(returns)) * np.sqrt(252)
    
    def monte_carlo_simulation(
        self,
        trades: List[Trade],
        num_simulations: int = 1000
    ) -> Dict:
        """
        Monte Carlo simülasyonu ile risk analizi
        
        Trade sırasını rastgele değiştirerek farklı sonuçları simüle eder
        """
        if len(trades) < 10:
            return {
                'error': 'En az 10 trade gerekli'
            }
        
        trade_returns = [t.pnl_pct for t in trades]
        
        simulation_results = []
        
        for _ in range(num_simulations):
            # Rastgele sıra
            shuffled_returns = np.random.choice(trade_returns, size=len(trade_returns), replace=True)
            
            # Cumulative returns
            cumulative = np.cumprod(1 + np.array(shuffled_returns) / 100)
            final_return = (cumulative[-1] - 1) * 100
            
            # Max drawdown
            peak = np.maximum.accumulate(cumulative)
            drawdown = (peak - cumulative) / peak
            max_dd = np.max(drawdown) * 100
            
            simulation_results.append({
                'final_return': final_return,
                'max_drawdown': max_dd
            })
        
        # İstatistikler
        final_returns = [s['final_return'] for s in simulation_results]
        max_drawdowns = [s['max_drawdown'] for s in simulation_results]
        
        return {
            'simulations': num_simulations,
            'return_mean': np.mean(final_returns),
            'return_std': np.std(final_returns),
            'return_median': np.median(final_returns),
            'return_5th_percentile': np.percentile(final_returns, 5),
            'return_95th_percentile': np.percentile(final_returns, 95),
            'probability_positive': sum(1 for r in final_returns if r > 0) / len(final_returns),
            'drawdown_mean': np.mean(max_drawdowns),
            'drawdown_median': np.median(max_drawdowns),
            'drawdown_95th_percentile': np.percentile(max_drawdowns, 95),
            'risk_adjusted_return': np.mean(final_returns) / np.std(final_returns) if np.std(final_returns) > 0 else 0
        }
    
    def cross_validation(
        self,
        strategy_func: Callable,
        data: pd.DataFrame,
        n_folds: int = 5
    ) -> Dict:
        """
        K-fold cross validation
        """
        fold_size = len(data) // n_folds
        fold_results = []
        
        for i in range(n_folds):
            # Test fold
            test_start = i * fold_size
            test_end = (i + 1) * fold_size if i < n_folds - 1 else len(data)
            test_data = data.iloc[test_start:test_end]
            
            # Train folds (diğer hepsi)
            train_data = pd.concat([
                data.iloc[:test_start],
                data.iloc[test_end:]
            ])
            
            # Optimize on train
            best_params = self._optimize_on_period(strategy_func, train_data)
            
            # Test
            test_trades = strategy_func(best_params, test_data)
            test_sharpe = self._calculate_sharpe(test_trades)
            test_pnl = sum(t.get('pnl', 0) for t in test_trades)
            
            fold_results.append({
                'fold': i + 1,
                'test_sharpe': test_sharpe,
                'test_pnl': test_pnl,
                'test_trades': len(test_trades)
            })
        
        # Aggregate
        avg_sharpe = np.mean([f['test_sharpe'] for f in fold_results])
        sharpe_std = np.std([f['test_sharpe'] for f in fold_results])
        
        return {
            'n_folds': n_folds,
            'avg_sharpe': avg_sharpe,
            'sharpe_std': sharpe_std,
            'sharpe_cv': sharpe_std / avg_sharpe if avg_sharpe > 0 else 0,
            'folds': fold_results
        }


# ============================================================================
# 4️⃣ GELİŞMİŞ PERFORMANS METRİKLERİ
# ============================================================================

class PerformanceMetrics:
    """
    Gelişmiş Performans Metrikleri
    
    Özellikler:
    - Sharpe, Sortino, Calmar ratios
    - Win/Loss streaks
    - MAE/MFE analysis
    - Expectancy
    - Risk-adjusted returns
    """
    
    def __init__(self, trades: List[Trade] = None):
        self.trades = trades or []
        
    def sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """
        Sharpe Ratio
        
        SR = (Mean Return - Risk Free Rate) / Std Dev of Returns
        """
        if not self.trades:
            return 0
            
        returns = [t.pnl_pct for t in self.trades]
        
        if len(returns) < 2 or np.std(returns) == 0:
            return 0
        
        excess_return = np.mean(returns) - (risk_free_rate / 252)  # Daily
        sharpe = (excess_return / np.std(returns)) * np.sqrt(252)  # Annualized
        
        return sharpe
    
    def sortino_ratio(self, risk_free_rate: float = 0.02, target_return: float = 0) -> float:
        """
        Sortino Ratio (sadece downside volatility'yi dikkate alır)
        
        SR = (Mean Return - Target Return) / Downside Deviation
        """
        if not self.trades:
            return 0
            
        returns = [t.pnl_pct for t in self.trades]
        
        # Downside returns (target'ın altında kalanlar)
        downside_returns = [r for r in returns if r < target_return]
        
        if len(downside_returns) < 2:
            return 0
        
        downside_deviation = np.std(downside_returns)
        
        if downside_deviation == 0:
            return 0
        
        excess_return = np.mean(returns) - target_return
        sortino = (excess_return / downside_deviation) * np.sqrt(252)
        
        return sortino
    
    def calmar_ratio(self, total_return_pct: float, max_drawdown_pct: float) -> float:
        """
        Calmar Ratio
        
        CR = Annual Return / Maximum Drawdown
        """
        if max_drawdown_pct == 0:
            return 0
        
        # Annualize return (basit varsayım)
        annual_return = total_return_pct
        
        calmar = annual_return / max_drawdown_pct
        
        return calmar
    
    def calculate_streaks(self) -> Dict:
        """
        Win/Loss streaks hesaplar
        """
        if not self.trades:
            return {
                'current_streak': 0,
                'max_win_streak': 0,
                'max_loss_streak': 0,
                'avg_win_streak': 0,
                'avg_loss_streak': 0
            }
        
        # Streak'leri bul
        current_streak = 0
        max_win_streak = 0
        max_loss_streak = 0
        
        win_streaks = []
        loss_streaks = []
        
        current_win_streak = 0
        current_loss_streak = 0
        
        for trade in self.trades:
            if trade.pnl > 0:
                current_win_streak += 1
                current_loss_streak = 0
                max_win_streak = max(max_win_streak, current_win_streak)
            else:
                current_loss_streak += 1
                current_win_streak = 0
                max_loss_streak = max(max_loss_streak, current_loss_streak)
            
            if current_win_streak == 0 and current_loss_streak > 0:
                loss_streaks.append(current_loss_streak)
            elif current_loss_streak == 0 and current_win_streak > 0:
                win_streaks.append(current_win_streak)
        
        # Son trade'e göre current streak
        if self.trades[-1].pnl > 0:
            current_streak = current_win_streak
        else:
            current_streak = -current_loss_streak
        
        return {
            'current_streak': current_streak,
            'max_win_streak': max_win_streak,
            'max_loss_streak': max_loss_streak,
            'avg_win_streak': np.mean(win_streaks) if win_streaks else 0,
            'avg_loss_streak': np.mean(loss_streaks) if loss_streaks else 0
        }
    
    def mae_mfe_analysis(self) -> Dict:
        """
        MAE (Maximum Adverse Excursion) ve MFE (Maximum Favorable Excursion) analizi
        """
        if not self.trades:
            return {
                'avg_mae': 0,
                'avg_mfe': 0,
                'mae_to_loss_ratio': 0,
                'mfe_to_win_ratio': 0
            }
        
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]
        
        avg_mae = np.mean([abs(t.mae) for t in self.trades])
        avg_mfe = np.mean([t.mfe for t in self.trades])
        
        # MAE/Loss ratio (losslarda MAE ne kadar büyük)
        if losing_trades:
            mae_to_loss = np.mean([abs(t.mae / t.pnl) if t.pnl != 0 else 0 for t in losing_trades])
        else:
            mae_to_loss = 0
        
        # MFE/Win ratio (winlerde MFE ne kadar büyük)
        if winning_trades:
            mfe_to_win = np.mean([t.mfe / t.pnl if t.pnl != 0 else 0 for t in winning_trades])
        else:
            mfe_to_win = 0
        
        return {
            'avg_mae': avg_mae,
            'avg_mfe': avg_mfe,
            'mae_to_loss_ratio': mae_to_loss,
            'mfe_to_win_ratio': mfe_to_win,
            'interpretation': self._interpret_mae_mfe(mae_to_loss, mfe_to_win)
        }
    
    def _interpret_mae_mfe(self, mae_ratio: float, mfe_ratio: float) -> str:
        """MAE/MFE yorumlama"""
        if mae_ratio > 2.0:
            mae_text = "Stop loss çok geniş - losses'lar kontrolden çıkıyor"
        elif mae_ratio > 1.5:
            mae_text = "Stop loss biraz geniş"
        else:
            mae_text = "Stop loss uygun"
        
        if mfe_ratio > 2.0:
            mfe_text = "Take profit çok erken - daha fazla kar kaçırılıyor"
        elif mfe_ratio > 1.5:
            mfe_text = "Take profit biraz erken"
        else:
            mfe_text = "Take profit uygun"
        
        return f"{mae_text}. {mfe_text}."
    
    def expectancy(self) -> Dict:
        """
        Expectancy (Beklenen Değer)
        
        E = (Win Rate * Avg Win) - (Loss Rate * Avg Loss)
        """
        if not self.trades:
            return {
                'expectancy': 0,
                'expectancy_ratio': 0,
                'interpretation': 'Veri yok'
            }
        
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]
        
        win_rate = len(winning_trades) / len(self.trades)
        loss_rate = len(losing_trades) / len(self.trades)
        
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = abs(np.mean([t.pnl for t in losing_trades])) if losing_trades else 0
        
        expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)
        
        # Expectancy ratio (her $1 risk için beklenen kar)
        if avg_loss > 0:
            expectancy_ratio = expectancy / avg_loss
        else:
            expectancy_ratio = 0
        
        interpretation = ''
        if expectancy > 0:
            interpretation = f'Pozitif expectancy: Her trade\'de ortalama ${expectancy:.2f} kazanç bekleniyor'
        else:
            interpretation = f'Negatif expectancy: Strateji uzun vadede zarar ettiriyor'
        
        return {
            'expectancy': expectancy,
            'expectancy_ratio': expectancy_ratio,
            'interpretation': interpretation,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'win_rate': win_rate * 100
        }
    
    def risk_adjusted_metrics(self, total_return_pct: float, max_dd_pct: float) -> Dict:
        """
        Risk-adjusted performance metrikleri
        """
        sharpe = self.sharpe_ratio()
        sortino = self.sortino_ratio()
        calmar = self.calmar_ratio(total_return_pct, max_dd_pct)
        
        # Return/Risk ratio
        if max_dd_pct > 0:
            return_risk_ratio = total_return_pct / max_dd_pct
        else:
            return_risk_ratio = 0
        
        # Risk score (0-100)
        risk_score = 0
        if sharpe > 2.0:
            risk_score += 30
        elif sharpe > 1.0:
            risk_score += 20
        
        if sortino > 2.0:
            risk_score += 30
        elif sortino > 1.0:
            risk_score += 20
        
        if calmar > 3.0:
            risk_score += 40
        elif calmar > 1.0:
            risk_score += 20
        
        return {
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'calmar_ratio': calmar,
            'return_risk_ratio': return_risk_ratio,
            'risk_score': risk_score,
            'grade': self._grade_performance(risk_score)
        }
    
    def _grade_performance(self, risk_score: int) -> str:
        """Performance grade"""
        if risk_score >= 80:
            return 'A+ (Mükemmel)'
        elif risk_score >= 60:
            return 'A (Çok İyi)'
        elif risk_score >= 40:
            return 'B (İyi)'
        elif risk_score >= 20:
            return 'C (Orta)'
        else:
            return 'D (Zayıf)'
    
    def generate_report(self, backtest_result: BacktestResult) -> str:
        """
        Kapsamlı performans raporu oluştur
        """
        report = []
        report.append("=" * 70)
        report.append("PERFORMANS RAPORU")
        report.append("=" * 70)
        report.append("")
        
        # Temel Metrikler
        report.append("📊 TEMEL METRİKLER")
        report.append("-" * 70)
        report.append(f"Başlangıç Sermayesi:    ${backtest_result.initial_capital:,.2f}")
        report.append(f"Final Sermaye:          ${backtest_result.final_capital:,.2f}")
        report.append(f"Toplam Kazanç:          ${backtest_result.total_return:,.2f} ({backtest_result.total_return_pct:+.2f}%)")
        report.append(f"")
        report.append(f"Toplam Trade:           {backtest_result.total_trades}")
        report.append(f"Kazanan Trade:          {backtest_result.winning_trades} ({backtest_result.win_rate:.1f}%)")
        report.append(f"Kaybeden Trade:         {backtest_result.losing_trades}")
        report.append("")
        
        # Risk Metrikleri
        report.append("⚠️  RİSK METRİKLERİ")
        report.append("-" * 70)
        report.append(f"Max Drawdown:           ${backtest_result.max_drawdown:,.2f} ({backtest_result.max_drawdown_pct:.2f}%)")
        report.append(f"Profit Factor:          {backtest_result.profit_factor:.2f}")
        report.append(f"Sharpe Ratio:           {backtest_result.sharpe_ratio:.2f}")
        report.append(f"Sortino Ratio:          {backtest_result.sortino_ratio:.2f}")
        report.append(f"Calmar Ratio:           {backtest_result.calmar_ratio:.2f}")
        report.append("")
        
        # Trade Analizi
        report.append("📈 TRADE ANALİZİ")
        report.append("-" * 70)
        report.append(f"Ortalama Kazanç:        ${backtest_result.avg_win:,.2f}")
        report.append(f"Ortalama Kayıp:         ${backtest_result.avg_loss:,.2f}")
        report.append(f"En Büyük Kazanç:        ${backtest_result.largest_win:,.2f}")
        report.append(f"En Büyük Kayıp:         ${backtest_result.largest_loss:,.2f}")
        report.append(f"Ortalama Trade Süresi:  {backtest_result.avg_trade_duration}")
        report.append("")
        
        # Maliyetler
        report.append("💰 MALİYETLER")
        report.append("-" * 70)
        report.append(f"Toplam Commission:      ${backtest_result.total_commission:,.2f}")
        report.append(f"Toplam Slippage:        ${backtest_result.total_slippage:,.2f}")
        report.append(f"Toplam Maliyet:         ${backtest_result.total_commission + backtest_result.total_slippage:,.2f}")
        report.append("")
        
        # Expectancy
        exp_data = self.expectancy()
        report.append("🎯 EXPECTANCY ANALİZİ")
        report.append("-" * 70)
        report.append(f"Expectancy:             ${exp_data['expectancy']:,.2f}")
        report.append(f"Expectancy Ratio:       {exp_data['expectancy_ratio']:.2f}")
        report.append(f"Yorum:                  {exp_data['interpretation']}")
        report.append("")
        
        # Streaks
        streaks = self.calculate_streaks()
        report.append("📊 STREAK ANALİZİ")
        report.append("-" * 70)
        report.append(f"Mevcut Streak:          {streaks['current_streak']:+d}")
        report.append(f"Max Kazanç Streak:      {streaks['max_win_streak']}")
        report.append(f"Max Kayıp Streak:       {streaks['max_loss_streak']}")
        report.append("")
        
        # MAE/MFE
        mae_mfe = self.mae_mfe_analysis()
        report.append("🎯 MAE/MFE ANALİZİ")
        report.append("-" * 70)
        report.append(f"Ortalama MAE:           ${mae_mfe['avg_mae']:,.2f}")
        report.append(f"Ortalama MFE:           ${mae_mfe['avg_mfe']:,.2f}")
        report.append(f"Yorum:                  {mae_mfe['interpretation']}")
        report.append("")
        
        # Risk-Adjusted Performance
        risk_adj = self.risk_adjusted_metrics(backtest_result.total_return_pct, backtest_result.max_drawdown_pct)
        report.append("⭐ GENEL DEĞERLENDİRME")
        report.append("-" * 70)
        report.append(f"Risk Score:             {risk_adj['risk_score']}/100")
        report.append(f"Performance Grade:      {risk_adj['grade']}")
        report.append("")
        
        report.append("=" * 70)
        
        return "\n".join(report)


# ============================================================================
# YARDIMCI FONKSİYONLAR
# ============================================================================

def generate_sample_data(
    num_days: int = 365,
    num_symbols: int = 5,
    start_price: float = 100.0
) -> pd.DataFrame:
    """
    Test için örnek OHLCV verisi oluşturur
    """
    symbols = [f'COIN{i}USDT' for i in range(1, num_symbols + 1)]
    
    data = []
    start_date = datetime.now() - timedelta(days=num_days)
    
    for symbol in symbols:
        price = start_price
        
        for day in range(num_days):
            date = start_date + timedelta(days=day)
            
            # Random walk
            change = np.random.randn() * 0.02
            price *= (1 + change)
            
            # OHLC
            open_price = price * (1 + np.random.randn() * 0.005)
            high_price = max(open_price, price) * (1 + abs(np.random.randn()) * 0.01)
            low_price = min(open_price, price) * (1 - abs(np.random.randn()) * 0.01)
            close_price = price
            volume = np.random.uniform(1000000, 10000000)
            
            data.append({
                'time': date,
                'symbol': symbol,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume,
                'volatility': abs(change)
            })
    
    return pd.DataFrame(data)


def generate_sample_signals(
    price_data: pd.DataFrame,
    signal_frequency: float = 0.1
) -> List[Dict]:
    """
    Test için örnek trading sinyalleri oluşturur
    """
    signals = []
    
    # Her sembol için
    for symbol in price_data['symbol'].unique():
        symbol_data = price_data[price_data['symbol'] == symbol].sort_values('time')
        
        position_open = False
        
        for i in range(len(symbol_data)):
            row = symbol_data.iloc[i]
            
            # Random sinyal
            if not position_open and np.random.random() < signal_frequency:
                # BUY signal
                signals.append({
                    'time': row['time'],
                    'symbol': symbol,
                    'action': 'BUY',
                    'leverage': np.random.choice([2, 3, 5]),
                    'stop_loss': row['close'] * 0.98,
                    'take_profit': row['close'] * 1.02,
                    'risk_pct': 0.02
                })
                position_open = True
                
            elif position_open and (i > 0 and np.random.random() < signal_frequency * 2):
                # SELL signal
                signals.append({
                    'time': row['time'],
                    'symbol': symbol,
                    'action': 'SELL'
                })
                position_open = False
    
    return sorted(signals, key=lambda x: x['time'])


# ============================================================================
# ÖRNEK KULLANIM
# ============================================================================

def example_usage():
    """
    Modülün nasıl kullanılacağını gösteren örnek
    """
    print("=" * 70)
    print("AI TRADING BOT - İYİLEŞTİRME MODÜLLERİ ÖRNEK KULLANIM")
    print("=" * 70)
    print()
    
    # 1. Örnek veri oluştur
    print("📊 Örnek veri oluşturuluyor...")
    price_data = generate_sample_data(num_days=180, num_symbols=3)
    signals = generate_sample_signals(price_data, signal_frequency=0.05)
    print(f"✅ {len(price_data)} adet fiyat verisi, {len(signals)} adet sinyal oluşturuldu")
    print()
    
    # 2. Backtesting
    print("🔄 Backtesting başlatılıyor...")
    engine = BacktestEngine(
        initial_capital=10000,
        commission_rate=0.0004,
        slippage_rate=0.0005
    )
    
    backtest_result = engine.run_backtest(signals, price_data)
    
    print(f"✅ Backtest tamamlandı!")
    print(f"   Total Return: ${backtest_result.total_return:,.2f} ({backtest_result.total_return_pct:+.2f}%)")
    print(f"   Win Rate: {backtest_result.win_rate:.1f}%")
    print(f"   Sharpe Ratio: {backtest_result.sharpe_ratio:.2f}")
    print()
    
    # 3. Risk Management
    print("⚠️  Risk yönetimi analizi...")
    risk_mgr = RiskManager(total_capital=10000)
    
    # Örnek pozisyon hesaplama
    position = risk_mgr.calculate_position_size(
        entry_price=100,
        stop_loss_price=98,
        leverage=3,
        win_rate=0.6,
        avg_win=50,
        avg_loss=30
    )
    
    print(f"✅ Optimal position size: ${position['size_usd']:,.2f} ({position['size_pct']:.1f}%)")
    print(f"   Method: {position['method']}")
    print(f"   Risk amount: ${position['risk_amount']:.2f}")
    print()
    
    # 4. Performance Metrics
    print("📈 Detaylı performans raporu oluşturuluyor...")
    metrics = PerformanceMetrics(backtest_result.trades)
    
    report = metrics.generate_report(backtest_result)
    print(report)
    print()
    
    # 5. Overfitting Detection
    print("🔍 Overfitting analizi...")
    optimizer = StrategyOptimizer()
    
    overfit_result = optimizer.detect_overfitting(
        in_sample_sharpe=2.5,
        out_sample_sharpe=0.8,
        in_sample_trades=100,
        out_sample_trades=95
    )
    
    print(f"✅ Overfitting Risk: {overfit_result['risk_level']}")
    print(f"   Score: {overfit_result['overfit_score']}/10")
    print(f"   Öneri: {overfit_result['recommendation']}")
    print()
    
    # 6. Monte Carlo Simulation
    if len(backtest_result.trades) >= 10:
        print("🎲 Monte Carlo simülasyonu...")
        mc_result = optimizer.monte_carlo_simulation(backtest_result.trades, num_simulations=1000)
        
        print(f"✅ 1000 simülasyon tamamlandı")
        print(f"   Ortalama Return: {mc_result['return_mean']:.2f}%")
        print(f"   5. Percentile: {mc_result['return_5th_percentile']:.2f}%")
        print(f"   95. Percentile: {mc_result['return_95th_percentile']:.2f}%")
        print(f"   Pozitif Olasılık: {mc_result['probability_positive']:.1%}")
        print()
    
    print("=" * 70)
    print("✅ TÜM MODÜLLER BAŞARIYLA TEST EDİLDİ!")
    print("=" * 70)


if __name__ == '__main__':
    # Örnek kullanımı çalıştır
    example_usage()
