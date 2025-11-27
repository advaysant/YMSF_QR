import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from data_loader import load_daily_data, identify_instruments, get_all_data_files, get_expiry_date
import os
from tqdm import tqdm

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def calculate_daily_metrics(df, instruments_map, current_date):
    """
    Calculates daily metrics for each instrument set.
    """
    results = []
    
    # Pre-calculate expiry for this date (using one sample instrument or just logic)
    # Expiry depends on the instrument, but usually they share the same monthly expiry.
    # We'll calculate DTE per instrument set to be safe.
    
    # Pivot or filter for faster access
    # df has columns: date, time, exchange, name, ltp, total_trade_qty, etc.
    
    # We need to group by name to get daily stats
    # But we need to align CM, Fut1, Fut2 by time to calculate spread minute-by-minute?
    # Or just take daily avg prices?
    # Spread of averages != Average of spreads usually, but close.
    # However, "Identify spread's behavior" usually implies the spread time series.
    # Let's calculate minute-wise spread and then average it for the day.
    
    # Pivot to get columns per instrument
    # This might be expensive if we pivot everything.
    # Let's just filter for the names we care about.
    
    relevant_names = set()
    for v in instruments_map.values():
        relevant_names.add(v['cm'])
        relevant_names.add(v['fut1'])
        if v['fut2']:
            relevant_names.add(v['fut2'])
            
    df_rel = df[df['name'].isin(relevant_names)].copy()
    
    # Pivot: Index=time, Columns=name, Values=[ltp, total_trade_qty]
    # We need to handle duplicates if any. Assuming unique time-name pairs.
    
    # Check for duplicates
    if df_rel.duplicated(subset=['time', 'name']).any():
        # Aggregate duplicates?
        df_rel = df_rel.groupby(['time', 'name']).agg({
            'ltp': 'last', # Take last price
            'total_trade_qty': 'max' # Cumulative volume? 
            # Wait, 'total_trade_qty' usually is cumulative for the day in NSE data?
            # Or is it volume for that minute?
            # Let's check the data sample.
            # 09:15:00 qty=653, 09:16:00 qty=17560. It increases. So it is cumulative.
            # So daily volume = max(total_trade_qty) - min(total_trade_qty) 
            # OR just max(total_trade_qty) if it resets daily.
            # Usually it resets. So max is the total volume for the day.
        }).reset_index()
    
    # Pivot
    df_pivot = df_rel.pivot(index='time', columns='name', values=['ltp', 'total_trade_qty'])
    
    for cm_name, inst in instruments_map.items():
        fut1_name = inst['fut1']
        fut2_name = inst['fut2']
        
        if fut1_name not in df_pivot['ltp'].columns:
            continue
            
        # Extract series
        cm_price = df_pivot['ltp'][cm_name]
        fut1_price = df_pivot['ltp'][fut1_name]
        
        # Calculate spreads
        # Spread 1: CM - Fut1 (or Fut1 - CM). Problem says "cm_fut1".
        # Usually Cash-Future spread (Basis) is Spot - Future.
        # Or Future - Spot (Cost of Carry).
        # Let's use (Future - Spot) / Spot * 100 for percentage, or just diff.
        # Problem 1A says "Identify and plot... cm_fut1".
        # I will compute (Fut1 - CM).
        
        spread_cm_fut1 = fut1_price - cm_price
        
        # Spread 2: Fut1 - Fut2
        spread_fut1_fut2 = pd.Series(np.nan, index=df_pivot.index)
        if fut2_name and fut2_name in df_pivot['ltp'].columns:
            fut2_price = df_pivot['ltp'][fut2_name]
            spread_fut1_fut2 = fut2_price - fut1_price # Calendar spread (Far - Near)
            
        # Daily metrics
        avg_spread_cm_fut1 = spread_cm_fut1.mean()
        avg_spread_fut1_fut2 = spread_fut1_fut2.mean()
        
        # Volume
        # Total volume for the day is the max of total_trade_qty column
        vol_cm = df_pivot['total_trade_qty'][cm_name].max()
        vol_fut1 = df_pivot['total_trade_qty'][fut1_name].max()
        vol_fut2 = 0
        if fut2_name and fut2_name in df_pivot['total_trade_qty'].columns:
            vol_fut2 = df_pivot['total_trade_qty'][fut2_name].max()
            
        # Expiry
        # Calculate DTE for Fut1
        expiry_fut1 = get_expiry_date(fut1_name, current_date)
        dte = (expiry_fut1 - current_date).days
        
        results.append({
            'date': current_date,
            'name': cm_name,
            'avg_spread_cm_fut1': avg_spread_cm_fut1,
            'avg_spread_fut1_fut2': avg_spread_fut1_fut2,
            'vol_cm': vol_cm,
            'vol_fut1': vol_fut1,
            'vol_fut2': vol_fut2,
            'dte': dte
        })
        
    return pd.DataFrame(results)

def main():
    files = get_all_data_files()
    all_metrics = []
    
    print("Processing data files...")
    for filepath in tqdm(files):
        df = load_daily_data(filepath)
        current_date = df['date'].iloc[0]
        
        instruments = identify_instruments(df)
        daily_metrics = calculate_daily_metrics(df, instruments, current_date)
        all_metrics.append(daily_metrics)
        
    final_df = pd.concat(all_metrics, ignore_index=True)
    final_df.to_csv(os.path.join(OUTPUT_DIR, "aggregated_metrics.csv"), index=False)
    print("Aggregated metrics saved.")
    
    # --- Plotting ---
    
    # A. Spread vs DTE
    # We aggregate across all names to see the "overall index" behavior as requested?
    # "Identify spread’s behavior per constituent, overall index..."
    # So we should plot for individual names (maybe a few examples or a heatmap) AND the average across all names.
    
    # Filter out extreme outliers if any
    
    # 1. CM_FUT1 Spread vs DTE
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=final_df, x='dte', y='avg_spread_cm_fut1', label='Average across all stocks')
    plt.title('CM-Fut1 Spread vs Days to Expiry')
    plt.gca().invert_xaxis() # High DTE to Low DTE
    plt.savefig(os.path.join(OUTPUT_DIR, "plot_A1_cm_fut1_vs_dte.png"))
    plt.close()
    
    # 2. Fut1_Fut2 Spread vs DTE
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=final_df, x='dte', y='avg_spread_fut1_fut2', label='Average across all stocks')
    plt.title('Fut1-Fut2 Spread vs Days to Expiry')
    plt.gca().invert_xaxis()
    plt.savefig(os.path.join(OUTPUT_DIR, "plot_A2_fut1_fut2_vs_dte.png"))
    plt.close()
    
    # B. Volume Ratios vs DTE
    final_df['vol_ratio_cm_fut1'] = final_df['vol_cm'] / final_df['vol_fut1']
    final_df['vol_ratio_fut1_fut2'] = final_df['vol_fut1'] / final_df['vol_fut2']
    
    # Replace infs
    final_df.replace([np.inf, -np.inf], np.nan, inplace=True)
    
    # 1. CM/Fut1 Vol Ratio
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=final_df, x='dte', y='vol_ratio_cm_fut1')
    plt.title('Volume Ratio (CM / Fut1) vs Days to Expiry')
    plt.gca().invert_xaxis()
    plt.savefig(os.path.join(OUTPUT_DIR, "plot_B1_vol_ratio_cm_fut1.png"))
    plt.close()
    
    # 2. Fut1/Fut2 Vol Ratio
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=final_df, x='dte', y='vol_ratio_fut1_fut2')
    plt.title('Volume Ratio (Fut1 / Fut2) vs Days to Expiry')
    plt.gca().invert_xaxis()
    plt.savefig(os.path.join(OUTPUT_DIR, "plot_B2_vol_ratio_fut1_fut2.png"))
    plt.close()
    
    # C. Distribution of Spreads
    # "Across names, days_to_expiry"
    # Maybe a boxplot of spreads binned by DTE?
    
    # Bin DTE
    final_df['dte_bin'] = pd.cut(final_df['dte'], bins=10)
    
    plt.figure(figsize=(12, 6))
    sns.boxplot(data=final_df, x='dte_bin', y='avg_spread_cm_fut1')
    plt.title('Distribution of CM-Fut1 Spread across DTE')
    plt.xticks(rotation=45)
    plt.savefig(os.path.join(OUTPUT_DIR, "plot_C1_dist_cm_fut1.png"))
    plt.close()
    
    plt.figure(figsize=(12, 6))
    sns.boxplot(data=final_df, x='dte_bin', y='avg_spread_fut1_fut2')
    plt.title('Distribution of Fut1-Fut2 Spread across DTE')
    plt.xticks(rotation=45)
    plt.savefig(os.path.join(OUTPUT_DIR, "plot_C2_dist_fut1_fut2.png"))
    plt.close()

if __name__ == "__main__":
    main()
