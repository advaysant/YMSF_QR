import pandas as pd
import numpy as np
import os
from data_loader import load_daily_data, identify_instruments, get_all_data_files
from strategy import MeanReversionStrategy
from tqdm import tqdm

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Costs (Assumptions)
# Transaction Cost: 0.05% per leg? Or fixed?
# Slippage: 1 tick?
# Problem says: "take the most sensible assumption"
# Let's assume:
# Brokerage + Taxes ~ 0.02% per trade value.
# Slippage ~ 0.05% (conservative) or 1 tick.
# Let's use a fixed cost per lot or per unit.
# Or percentage of price.
# Let's use 0.05% of notional value per side (entry/exit) to cover everything.

COST_PCT = 0.0005 

def backtest_stock(stock_name, files, strategy):
    """
    Runs backtest for a single stock across all days.
    """
    # We need to process day by day, but carry over state?
    # Intraday strategy usually closes positions at end of day.
    # Problem doesn't specify. "n_traded_days" implies we trade on multiple days.
    # If mean reverting, intraday is safer.
    # Let's assume intraday trading: Close all positions at 15:29.
    
    daily_results = []
    
    total_pnl = 0
    total_gross_pnl = 0
    total_cost = 0
    total_slippage = 0
    total_lots = 0
    total_volume = 0
    max_delta_qty = 0 # Max net position?
    max_gross_qty = 0
    
    equity_curve = []
    
    # We need to load data for this stock across all files
    # This is inefficient if we load all files for each stock.
    # Better to iterate files and update all stocks.
    # But we want to output per stock.
    
    # Let's stick to the structure: Iterate files, update all active strategies.
    pass

def run_simulation():
    files = get_all_data_files()
    # Initialize strategy with 2-day lookback (750 minutes)
    strategy = MeanReversionStrategy(lookback_window=750, entry_percentile=0.95, exit_percentile=0.50)
    
    # Store results per stock
    stock_stats = {} 
    # { 'STOCK': { 'pnl': 0, ... } }
    
    # Store spread history for each stock to maintain continuity across days
    stock_buffers = {}
    
    print("Starting simulation...")
    for filepath in tqdm(files):
        df = load_daily_data(filepath)
        current_date = df['date'].iloc[0]
        
        instruments = identify_instruments(df)
        
        # Pivot for price access
        relevant_names = []
        for v in instruments.values():
            relevant_names.append(v['cm'])
            relevant_names.append(v['fut1'])
            
        df_rel = df[df['name'].isin(relevant_names)]
        
        if df_rel.duplicated(subset=['time', 'name']).any():
            df_rel = df_rel.groupby(['time', 'name']).agg({'ltp': 'last', 'lot_size': 'max'}).reset_index()
            
        pivot = df_rel.pivot(index='time', columns='name', values='ltp')
        lot_sizes = df_rel.groupby('name')['lot_size'].first().to_dict()
        
        for cm_name, inst in instruments.items():
            fut1_name = inst['fut1']
            
            if cm_name not in pivot.columns or fut1_name not in pivot.columns:
                continue
                
            cm_prices = pivot[cm_name]
            fut1_prices = pivot[fut1_name]
            
            # Spread = Fut1 - CM
            spread = fut1_prices - cm_prices
            
            # Maintain continuity: concatenate with previous days' data
            if cm_name not in stock_buffers:
                stock_buffers[cm_name] = pd.Series(dtype=float)
            
            # Combine historical data with current day
            full_spread = pd.concat([stock_buffers[cm_name], spread])
            
            # Generate signals on the full series
            positions_full = strategy.generate_signals(full_spread)
            
            # Extract positions for current day only
            positions = positions_full.iloc[-len(spread):]
            
            # Update buffer (keep last 2000 points to avoid memory issues)
            stock_buffers[cm_name] = full_spread.iloc[-2000:]
            
            # Calculate PnL
            lot_size = lot_sizes.get(fut1_name, 1)
            
            spread_diff = spread.diff()
            pnl_series = positions.shift(1) * spread_diff * lot_size
            
            trades = positions.diff().abs()
            trade_costs = trades * (cm_prices * 2) * lot_size * COST_PCT
            
            daily_pnl = pnl_series.sum()
            daily_cost = trade_costs.sum()
            daily_net_pnl = daily_pnl - daily_cost
            
            # Update stats
            if cm_name not in stock_stats:
                stock_stats[cm_name] = {
                    'n_traded_days': 0,
                    'net_pnl': 0,
                    'gross_pnl': 0,
                    'cost_pnl': 0,
                    'slippage_fut1': 0,
                    'slippage_fut2': 0,
                    'total_lots_traded': 0,
                    'total_volume': 0,
                    'max_delta_qty': 0,
                    'max_gross_qty': 0,
                    'drawdown': 0,
                    'equity': []
                }
            
            stats = stock_stats[cm_name]
            
            if trades.sum() > 0:
                stats['n_traded_days'] += 1
                
            stats['gross_pnl'] += daily_pnl
            stats['cost_pnl'] += daily_cost
            stats['net_pnl'] += daily_net_pnl
            stats['total_lots_traded'] += trades.sum()
            stats['equity'].append(daily_net_pnl)
            
    # Finalize stats
    results_list = []
    total_market_lots = sum(s['total_lots_traded'] for s in stock_stats.values())
    
    for stock, stats in stock_stats.items():
        # Calculate drawdown
        equity_curve = np.cumsum(stats['equity'])
        if len(equity_curve) > 0:
            peak = np.maximum.accumulate(equity_curve)
            dd = peak - equity_curve
            max_dd = dd.max()
        else:
            max_dd = 0
            
        market_perc = stats['total_lots_traded'] / total_market_lots if total_market_lots > 0 else 0
        
        results_list.append({
            'stock_name': stock,
            'n_traded_days': stats['n_traded_days'],
            'net_pnl': stats['net_pnl'],
            'gross_pnl': stats['gross_pnl'],
            'cost_pnl': stats['cost_pnl'],
            'slippage_fut1': 0,
            'slippage_fut2': 0,
            'total_lots_traded': stats['total_lots_traded'],
            'total_volume': 0, # Placeholder
            'max_delta_qty': 0, # Placeholder
            'max_gross_qty': 0, # Placeholder
            'drawdown': max_dd,
            'market_perc': market_perc
        })
        
    results_df = pd.DataFrame(results_list)
    results_df.sort_values('net_pnl', ascending=False, inplace=True)
    results_df.to_csv(os.path.join(OUTPUT_DIR, "Results.csv"), index=False)
    print("Results saved to Results.csv")

if __name__ == "__main__":
    run_simulation()
