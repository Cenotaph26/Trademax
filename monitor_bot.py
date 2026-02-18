#!/usr/bin/env python3
"""
Bot Monitoring Script - Claude can fetch live data from bot
Usage: python3 monitor_bot.py
"""

import requests
import json
from datetime import datetime

BOT_URL = "https://trademax-production.up.railway.app"

def get_debug_data():
    """Fetch full debug data from bot"""
    try:
        r = requests.get(f"{BOT_URL}/api/debug", timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def analyze_bot_health(data):
    """Analyze bot performance and detect issues"""
    if 'error' in data:
        return {"status": "ERROR", "issues": [data['error']]}
    
    issues = []
    warnings = []
    
    # Check win rate
    if data['win_rate'] < 30:
        issues.append(f"❌ Low win rate: {data['win_rate']}% (target: >40%)")
    elif data['win_rate'] < 45:
        warnings.append(f"⚠️ Win rate below target: {data['win_rate']}% (target: >45%)")
    
    # Check drawdown
    if data['drawdown'] > 25:
        issues.append(f"❌ High drawdown: {data['drawdown']}% (max: 25%)")
    elif data['drawdown'] > 15:
        warnings.append(f"⚠️ Elevated drawdown: {data['drawdown']}%")
    
    # Check profit factor
    if data['profit_factor'] < 1.0:
        issues.append(f"❌ Losing overall: Profit factor {data['profit_factor']}")
    elif data['profit_factor'] < 1.5:
        warnings.append(f"⚠️ Low profit factor: {data['profit_factor']} (target: >1.5)")
    
    # Check position health
    stuck_positions = 0
    for sym, pos in data['positions_detail'].items():
        # Position stuck at SL distance
        if pos['sl_distance_pct'] < 0.3 and pos['pnl'] < 0:
            stuck_positions += 1
        # Position duration too long
        if pos['duration_sec'] > 7200 and pos['pnl'] < 0:  # 2 hours
            warnings.append(f"⚠️ {sym} stuck for {pos['duration_sec']//60}min with {pos['pnl']:.1f} PnL")
    
    if stuck_positions > 2:
        issues.append(f"❌ {stuck_positions} positions stuck near SL")
    
    # Check strategy balance
    best_wr = max([s['win_rate'] for s in data['strategies'].values()]) if data['strategies'] else 0
    worst_wr = min([s['win_rate'] for s in data['strategies'].values()]) if data['strategies'] else 0
    if best_wr - worst_wr > 40:
        warnings.append(f"⚠️ Strategy imbalance: {best_wr:.0f}% vs {worst_wr:.0f}%")
    
    return {
        "status": "CRITICAL" if issues else "WARNING" if warnings else "HEALTHY",
        "issues": issues,
        "warnings": warnings
    }

def generate_report(data):
    """Generate human-readable report"""
    print("="*60)
    print("🤖 BOT HEALTH REPORT")
    print("="*60)
    print(f"Timestamp: {data.get('timestamp', 'N/A')}")
    print(f"Uptime: {data.get('uptime_seconds', 0)//60} minutes")
    print(f"Status: {'🟢 RUNNING' if data.get('running') else '🔴 STOPPED'}")
    print()
    
    print("💰 PERFORMANCE:")
    print(f"  Balance: ${data['balance']:,.2f} (Start: ${data['start_balance']:,.2f})")
    print(f"  Total PnL: ${data['total_pnl']:,.2f} ({data['total_pnl_pct']:+.2f}%)")
    print(f"  Drawdown: {data['drawdown']}%")
    print(f"  Profit Factor: {data['profit_factor']}")
    print()
    
    print("📊 TRADING STATS:")
    print(f"  Trades: {data['trades']} (W:{data['wins']} / L:{data['losses']})")
    print(f"  Win Rate: {data['win_rate']:.1f}%")
    print(f"  Active Positions: {data['active_positions']}")
    print(f"  Total Profit: ${data['total_profit']:,.2f}")
    print(f"  Total Loss: ${data['total_loss']:,.2f}")
    print()
    
    print("🎯 STRATEGIES:")
    for name, info in sorted(data['strategies'].items(), key=lambda x: x[1]['win_rate'], reverse=True):
        print(f"  {name:20s} WR:{info['win_rate']:5.1f}% Trades:{info['trades']:3d} Score:{info['score']:.2f}")
    print()
    
    # Health analysis
    health = analyze_bot_health(data)
    print(f"🏥 HEALTH STATUS: {health['status']}")
    if health['issues']:
        print("\n❌ CRITICAL ISSUES:")
        for issue in health['issues']:
            print(f"  {issue}")
    if health['warnings']:
        print("\n⚠️  WARNINGS:")
        for warning in health['warnings']:
            print(f"  {warning}")
    
    if not health['issues'] and not health['warnings']:
        print("  ✅ All systems nominal")
    
    print()
    print("="*60)
    
    return health

if __name__ == "__main__":
    print("Fetching bot data...\n")
    data = get_debug_data()
    
    if 'error' in data and 'Engine' not in str(data['error']):
        print(f"❌ Connection error: {data['error']}")
    else:
        health = generate_report(data)
        
        # Save to file for Claude to read
        with open('/tmp/bot_report.json', 'w') as f:
            json.dump({
                'data': data,
                'health': health,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)
        
        print("\n📄 Report saved to /tmp/bot_report.json")
        print(f"🔗 Debug endpoint: {BOT_URL}/api/debug")
