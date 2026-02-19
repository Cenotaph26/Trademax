"""
🔴 CANLI BOT İZLEME SİSTEMİ
============================

Bu sistem botunuzu gerçek zamanlı izler ve sizin sorularınıza göre
anlık analizler ve iyileştirme önerileri sunar.

Kullanım:
---------
1. Bu dosyayı trading_bot_v5.py ile aynı klasöre koyun
2. Botu başlatın
3. Web arayüzünde /api/live-status endpoint'ini kullanın
4. Bana "botu incele", "ne yapmalıyım", "sorun var mı" gibi sorular sorun
"""

import json
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import threading


class LiveBotAnalyzer:
    """
    Botu gerçek zamanlı izler ve Claude'a analiz için veri sağlar
    """
    
    def __init__(self, engine):
        self.engine = engine
        self.agent = engine.agent
        
        # Snapshot history (son 1 saat)
        self.snapshots = []
        self.max_snapshots = 360  # 10 saniyede bir = 1 saat
        
        # İzleme başlat
        self.is_running = False
        self.monitor_thread = None
        
        print("🔴 Canlı İzleme Sistemi hazır")
    
    def start_monitoring(self):
        """İzlemeyi başlat"""
        if self.is_running:
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("🔴 Canlı izleme başlatıldı - Her 10 saniyede snapshot alınıyor")
    
    def stop_monitoring(self):
        """İzlemeyi durdur"""
        self.is_running = False
        print("⏹️  Canlı izleme durduruldu")
    
    def _monitor_loop(self):
        """Her 10 saniyede snapshot al"""
        while self.is_running:
            try:
                snapshot = self.take_snapshot()
                self.snapshots.append(snapshot)
                
                # Son 1 saati tut
                if len(self.snapshots) > self.max_snapshots:
                    self.snapshots.pop(0)
                
            except Exception as e:
                print(f"⚠️  Snapshot error: {e}")
            
            time.sleep(10)  # 10 saniyede bir
    
    def take_snapshot(self) -> Dict:
        """Anlık durum snapshot'ı"""
        try:
            # Risk Manager metrics (eğer varsa)
            if hasattr(self.agent, 'risk_manager') and self.agent.risk_manager:
                portfolio_heat = self.agent.risk_manager.calculate_portfolio_heat()
                current_drawdown = self.agent.risk_manager.current_drawdown
            else:
                portfolio_heat = 0
                current_drawdown = self.agent.drawdown() / 100
            
            # Performance metrics (eğer varsa)
            if hasattr(self.agent, 'all_trades') and len(self.agent.all_trades) >= 10:
                from trading_bot_improvements import PerformanceMetrics
                metrics = PerformanceMetrics(self.agent.all_trades)
                sharpe = metrics.sharpe_ratio()
                sortino = metrics.sortino_ratio()
                exp_data = metrics.expectancy()
                expectancy = exp_data['expectancy']
            else:
                sharpe = 0
                sortino = 0
                expectancy = 0
            
            snapshot = {
                'timestamp': datetime.now().isoformat(),
                'balance': round(self.agent.balance, 2),
                'total_pnl': round(self.agent.total_pnl(), 2),
                'total_pnl_pct': round((self.agent.balance - self.agent.start_balance) / self.agent.start_balance * 100, 2),
                'open_positions': len(self.agent.positions),
                'total_trades': self.agent.trades,
                'wins': self.agent.wins,
                'losses': self.agent.trades - self.agent.wins,
                'win_rate': round(self.agent.wr(), 2),
                'profit_factor': round(self.agent.profit_factor(), 2),
                'drawdown_pct': round(current_drawdown * 100, 2),
                'portfolio_heat_pct': round(portfolio_heat * 100, 2),
                'sharpe_ratio': round(sharpe, 2),
                'sortino_ratio': round(sortino, 2),
                'expectancy': round(expectancy, 2),
                'bot_running': self.engine.running,
                'tick': self.engine.tick,
                
                # Açık pozisyonlar detay
                'positions_detail': [
                    {
                        'symbol': sym,
                        'type': pos['type'],
                        'entry': pos['entry'],
                        'current': pos['cur'],
                        'pnl': round(pos['pnl'], 2),
                        'pnl_pct': round(pos['pnl_pct'], 2),
                        'leverage': pos['lev'],
                        'duration_minutes': int((datetime.now() - datetime.fromisoformat(pos['t0'])).total_seconds() / 60)
                    }
                    for sym, pos in self.agent.positions.items()
                ],
                
                # Son 5 trade
                'recent_trades': self.agent.history[:5] if self.agent.history else []
            }
            
            return snapshot
            
        except Exception as e:
            print(f"⚠️  Snapshot error: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def get_current_status(self) -> Dict:
        """Anlık durum raporu"""
        snapshot = self.take_snapshot()
        
        # Trend analizi (son 10 dakika)
        recent_snapshots = self.snapshots[-60:] if len(self.snapshots) >= 60 else self.snapshots
        
        if len(recent_snapshots) >= 2:
            balance_trend = recent_snapshots[-1]['balance'] - recent_snapshots[0]['balance']
            balance_trend_pct = (balance_trend / recent_snapshots[0]['balance']) * 100
        else:
            balance_trend = 0
            balance_trend_pct = 0
        
        return {
            'current': snapshot,
            'trend_10min': {
                'balance_change': round(balance_trend, 2),
                'balance_change_pct': round(balance_trend_pct, 2),
                'samples': len(recent_snapshots)
            },
            'history_1hour': {
                'total_snapshots': len(self.snapshots),
                'oldest': self.snapshots[0]['timestamp'] if self.snapshots else None,
                'newest': self.snapshots[-1]['timestamp'] if self.snapshots else None
            }
        }
    
    def analyze_for_claude(self) -> Dict:
        """
        Claude'un analiz yapması için kapsamlı veri paketi
        """
        current = self.take_snapshot()
        
        # Son 1 saatin analizi
        if len(self.snapshots) >= 2:
            first = self.snapshots[0]
            last = self.snapshots[-1]
            
            time_diff = (datetime.fromisoformat(last['timestamp']) - 
                        datetime.fromisoformat(first['timestamp'])).total_seconds() / 3600
            
            balance_change = last['balance'] - first['balance']
            balance_change_pct = (balance_change / first['balance']) * 100
            
            trades_in_period = last['total_trades'] - first['total_trades']
            trades_per_hour = trades_in_period / time_diff if time_diff > 0 else 0
            
            # Win rate değişimi
            win_rate_change = last['win_rate'] - first['win_rate']
            
            # Drawdown trendi
            dd_change = last['drawdown_pct'] - first['drawdown_pct']
        else:
            balance_change = 0
            balance_change_pct = 0
            trades_in_period = 0
            trades_per_hour = 0
            win_rate_change = 0
            dd_change = 0
        
        # Sorun tespiti
        issues = []
        warnings = []
        
        # 1. Drawdown kontrolü
        if current['drawdown_pct'] > 15:
            issues.append(f"❌ Yüksek drawdown: {current['drawdown_pct']:.1f}% (limit: 15%)")
        elif current['drawdown_pct'] > 10:
            warnings.append(f"⚠️  Drawdown yükseliyor: {current['drawdown_pct']:.1f}%")
        
        # 2. Win rate kontrolü
        if current['total_trades'] >= 10 and current['win_rate'] < 40:
            issues.append(f"❌ Düşük win rate: {current['win_rate']:.1f}% (min: 40%)")
        elif current['total_trades'] >= 10 and current['win_rate'] < 50:
            warnings.append(f"⚠️  Win rate düşük: {current['win_rate']:.1f}%")
        
        # 3. Portfolio heat
        if current['portfolio_heat_pct'] > 12:
            issues.append(f"❌ Portfolio risk çok yüksek: {current['portfolio_heat_pct']:.1f}%")
        elif current['portfolio_heat_pct'] > 8:
            warnings.append(f"⚠️  Portfolio risk yükseliyor: {current['portfolio_heat_pct']:.1f}%")
        
        # 4. Profit factor
        if current['total_trades'] >= 10 and current['profit_factor'] < 1.0:
            issues.append(f"❌ Negatif profit factor: {current['profit_factor']:.2f}")
        elif current['total_trades'] >= 10 and current['profit_factor'] < 1.5:
            warnings.append(f"⚠️  Düşük profit factor: {current['profit_factor']:.2f}")
        
        # 5. Sharpe ratio
        if current['total_trades'] >= 20 and current['sharpe_ratio'] < 0:
            issues.append(f"❌ Negatif Sharpe ratio: {current['sharpe_ratio']:.2f}")
        elif current['total_trades'] >= 20 and current['sharpe_ratio'] < 0.5:
            warnings.append(f"⚠️  Düşük Sharpe ratio: {current['sharpe_ratio']:.2f}")
        
        # 6. Açık pozisyonlar
        for pos in current['positions_detail']:
            if pos['duration_minutes'] > 1440:  # 24 saat
                warnings.append(f"⚠️  {pos['symbol']}: {pos['duration_minutes']/60:.1f} saattir açık")
            
            if pos['pnl_pct'] < -5:
                warnings.append(f"⚠️  {pos['symbol']}: %{pos['pnl_pct']:.1f} zararda")
        
        # 7. Trade frequency
        if trades_per_hour > 5:
            warnings.append(f"⚠️  Çok fazla trade: {trades_per_hour:.1f}/saat")
        elif current['total_trades'] >= 5 and trades_per_hour < 0.1:
            warnings.append(f"⚠️  Çok az trade: {trades_per_hour:.2f}/saat")
        
        # 8. Son trade'ler
        if current['recent_trades']:
            recent_5 = current['recent_trades'][:5]
            recent_losses = sum(1 for t in recent_5 if not t['won'])
            if recent_losses >= 4:
                warnings.append(f"⚠️  Son 5 trade'den {recent_losses} kayıp")
        
        # Sağlık skoru (0-100)
        health_score = 100
        health_score -= len(issues) * 20
        health_score -= len(warnings) * 5
        health_score = max(0, health_score)
        
        # Genel durum
        if health_score >= 80:
            status = "🟢 EXCELLENT"
        elif health_score >= 60:
            status = "🟡 GOOD"
        elif health_score >= 40:
            status = "🟠 WARNING"
        else:
            status = "🔴 CRITICAL"
        
        return {
            'timestamp': datetime.now().isoformat(),
            'status': status,
            'health_score': health_score,
            
            # Mevcut durum
            'current_state': current,
            
            # Trendler (son 1 saat)
            'trends': {
                'balance_change': round(balance_change, 2),
                'balance_change_pct': round(balance_change_pct, 2),
                'trades_in_period': trades_in_period,
                'trades_per_hour': round(trades_per_hour, 2),
                'win_rate_change': round(win_rate_change, 2),
                'drawdown_change': round(dd_change, 2),
            },
            
            # Sorunlar
            'issues': issues,
            'warnings': warnings,
            
            # Öneriler (basit)
            'quick_suggestions': self._generate_quick_suggestions(current, issues, warnings)
        }
    
    def _generate_quick_suggestions(self, current: Dict, issues: List, warnings: List) -> List[str]:
        """Hızlı öneriler"""
        suggestions = []
        
        if current['drawdown_pct'] > 10:
            suggestions.append("Position size'ı küçült (örn: %9 -> %6)")
            suggestions.append("Stop loss'ları sıkılaştır")
        
        if current['win_rate'] < 50 and current['total_trades'] >= 10:
            suggestions.append("Entry kriterlerini sıkılaştır (min_score artır)")
            suggestions.append("Confirmation sayısını artır")
        
        if current['portfolio_heat_pct'] > 8:
            suggestions.append("Max positions sayısını azalt (7 -> 5)")
            suggestions.append("Yeni pozisyon açma")
        
        if current['profit_factor'] < 1.5 and current['total_trades'] >= 10:
            suggestions.append("Take profit hedefini artır")
            suggestions.append("Trailing stop kullan")
        
        if len(issues) >= 2:
            suggestions.append("🛑 BOTU DURDUR - Ciddi sorunlar var")
        
        return suggestions
    
    def get_detailed_report(self) -> str:
        """Claude için detaylı metin raporu"""
        analysis = self.analyze_for_claude()
        current = analysis['current_state']
        trends = analysis['trends']
        
        report = []
        report.append("=" * 70)
        report.append(f"🔴 CANLI BOT ANALİZİ - {analysis['status']}")
        report.append(f"Sağlık Skoru: {analysis['health_score']}/100")
        report.append("=" * 70)
        report.append("")
        
        # Temel Metrikler
        report.append("📊 TEMEL METRİKLER")
        report.append("-" * 70)
        report.append(f"Sermaye:          ${current['balance']:,.2f} ({current['total_pnl_pct']:+.2f}%)")
        report.append(f"Toplam Trade:     {current['total_trades']} ({current['wins']}W / {current['losses']}L)")
        report.append(f"Win Rate:         {current['win_rate']:.1f}%")
        report.append(f"Profit Factor:    {current['profit_factor']:.2f}")
        report.append(f"Drawdown:         {current['drawdown_pct']:.2f}%")
        report.append(f"Portfolio Heat:   {current['portfolio_heat_pct']:.2f}%")
        report.append(f"Sharpe Ratio:     {current['sharpe_ratio']:.2f}")
        report.append(f"Sortino Ratio:    {current['sortino_ratio']:.2f}")
        report.append(f"Expectancy:       ${current['expectancy']:.2f}")
        report.append("")
        
        # Trendler
        report.append("📈 TRENDLER (Son 1 Saat)")
        report.append("-" * 70)
        report.append(f"Balance Değişimi:     ${trends['balance_change']:+,.2f} ({trends['balance_change_pct']:+.2f}%)")
        report.append(f"Trade Frequency:      {trends['trades_per_hour']:.2f}/saat")
        report.append(f"Win Rate Değişimi:    {trends['win_rate_change']:+.2f}%")
        report.append(f"Drawdown Değişimi:    {trends['drawdown_change']:+.2f}%")
        report.append("")
        
        # Açık Pozisyonlar
        if current['positions_detail']:
            report.append(f"📍 AÇIK POZİSYONLAR ({len(current['positions_detail'])})")
            report.append("-" * 70)
            for pos in current['positions_detail']:
                emoji = "🟢" if pos['pnl'] > 0 else "🔴"
                report.append(f"{emoji} {pos['symbol']} {pos['type']} | ${pos['pnl']:+.2f} ({pos['pnl_pct']:+.2f}%) | {pos['duration_minutes']}dk | {pos['leverage']}x")
            report.append("")
        
        # Son Tradeler
        if current['recent_trades']:
            report.append("🕐 SON 5 TRADE")
            report.append("-" * 70)
            for trade in current['recent_trades'][:5]:
                emoji = "✅" if trade['won'] else "❌"
                report.append(f"{emoji} {trade['sym']} {trade['type']} | ${trade['pnl']:+.2f} ({trade['pnl_pct']:+.2f}%) | {trade['why']} | {trade['time']}")
            report.append("")
        
        # Sorunlar
        if analysis['issues']:
            report.append("🔴 KRİTİK SORUNLAR")
            report.append("-" * 70)
            for issue in analysis['issues']:
                report.append(issue)
            report.append("")
        
        # Uyarılar
        if analysis['warnings']:
            report.append("⚠️  UYARILAR")
            report.append("-" * 70)
            for warning in analysis['warnings']:
                report.append(warning)
            report.append("")
        
        # Öneriler
        if analysis['quick_suggestions']:
            report.append("💡 HIZLI ÖNERİLER")
            report.append("-" * 70)
            for i, suggestion in enumerate(analysis['quick_suggestions'], 1):
                report.append(f"{i}. {suggestion}")
            report.append("")
        
        report.append("=" * 70)
        report.append(f"Rapor Zamanı: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 70)
        
        return "\n".join(report)


# ============================================================================
# Web API Entegrasyonu
# ============================================================================

def add_monitoring_endpoints(engine):
    """
    Mevcut web server'a monitoring endpoint'leri ekle
    
    Usage:
        engine = Engine()
        add_monitoring_endpoints(engine)
        engine.start()
    """
    
    # Analyzer oluştur
    analyzer = LiveBotAnalyzer(engine)
    analyzer.start_monitoring()
    
    # Mevcut HTTPHandler'a yeni endpoint'ler ekle
    original_do_GET = engine.server_handler_class.do_GET if hasattr(engine, 'server_handler_class') else None
    
    def enhanced_do_GET(self):
        path = urlparse(self.path).path
        
        if path == '/api/live-status':
            # Anlık durum
            status = analyzer.get_current_status()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(status).encode())
            
        elif path == '/api/live-analysis':
            # Detaylı analiz (JSON)
            analysis = analyzer.analyze_for_claude()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(analysis).encode())
            
        elif path == '/api/live-report':
            # Detaylı rapor (Text)
            report = analyzer.get_detailed_report()
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(report.encode('utf-8'))
            
        elif path == '/api/snapshot':
            # Tek snapshot
            snapshot = analyzer.take_snapshot()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(snapshot).encode())
            
        else:
            # Orijinal handler'a devret
            if original_do_GET:
                original_do_GET(self)
    
    # HTTPHandler class'ını güncelle (eğer varsa)
    if hasattr(engine, 'server_handler_class'):
        engine.server_handler_class.do_GET = enhanced_do_GET
    
    return analyzer


# ============================================================================
# Kullanım Örneği
# ============================================================================

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║          🔴 CANLI BOT İZLEME SİSTEMİ                        ║
    ╚══════════════════════════════════════════════════════════════╝
    
    Bu modül trading_bot_v5.py ile entegre edilmelidir.
    
    Entegrasyon:
    -----------
    1. trading_bot_v5.py'nin sonuna ekleyin:
    
        from live_bot_monitor import add_monitoring_endpoints
        
        if __name__ == '__main__':
            engine = Engine()
            
            # İzleme ekle
            analyzer = add_monitoring_endpoints(engine)
            
            engine.start()
    
    2. API Endpoints:
       - /api/live-status      → Anlık durum (JSON)
       - /api/live-analysis    → Detaylı analiz (JSON)
       - /api/live-report      → Metin rapor (Text)
       - /api/snapshot         → Tek snapshot (JSON)
    
    3. Kullanım:
       Bana "botu incele" dediğinizde, ben bu API'lerden veri çekip
       analiz yapacağım ve size öneriler sunacağım.
    
    Örnek Sorular:
    -------------
    - "Botu incele, nasıl gidiyor?"
    - "Sorun var mı?"
    - "Win rate neden düşük?"
    - "Drawdown'u nasıl azaltırım?"
    - "Position size'ı değiştirmeli miyim?"
    - "Hangi parametreleri ayarlayayım?"
    """)
