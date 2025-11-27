import pandas as pd
import os
import glob
from datetime import datetime, timedelta
import re

DATA_DIR = "customdata_new/trading.end_time__15-30-00"

def get_expiry_date(symbol, current_date):
    """
    Approximates expiry date.
    Assumption: Expiry is the last Thursday of the month.
    The symbol usually contains the month and year, e.g., GAIL25FEBFUT.
    However, we need to determine which month the future belongs to.
    
    Actually, simpler approach:
    The problem says: "Days To Expiry in this context - means days left for the near future (Fut1). Assume expiry date for every instrument to be the last thursday of the current month."
    
    So for any given date, we just need to find the last Thursday of that month.
    If the current date is past the last Thursday, then we look at the next month?
    Wait, "current month" usually implies the month of the trading date.
    But if we are trading near end of month, near future might be next month.
    
    Let's look at the data.
    20250217.data.csv -> Feb 17, 2025.
    Near future is likely Feb expiry.
    
    Let's implement a function to get the last Thursday of a month.
    """
    # This is a simplification. Ideally we parse the symbol, but the problem statement says
    # "Assume expiry date for every instrument to be the last thursday of the current month."
    # This implies we calculate DTE based on the current date's month end.
    
    # However, if we are on Feb 28 (Friday) and last Thursday was Feb 27, then "current month expiry" is passed.
    # But usually near future would roll over.
    
    # Let's stick to the instruction: "Assume expiry date for every instrument to be the last thursday of the current month."
    # This might be a simplification for the assignment.
    
    year = current_date.year
    month = current_date.month
    
    last_day = pd.Timestamp(year, month, 1) + pd.offsets.MonthEnd(1)
    # Go back to Thursday
    offset = (last_day.weekday() - 3) % 7
    expiry = last_day - pd.Timedelta(days=offset)
    
    if current_date > expiry:
        # If we are past expiry, maybe the "current month" instruction implies next month?
        # Or maybe the data doesn't go past expiry for that contract?
        # Let's assume next month if passed.
        next_month = current_date + pd.offsets.MonthBegin(1)
        last_day = next_month + pd.offsets.MonthEnd(1)
        offset = (last_day.weekday() - 3) % 7
        expiry = last_day - pd.Timedelta(days=offset)
        
    return expiry

def load_daily_data(filepath):
    """
    Loads a single daily CSV file.
    Extracts date from filename.
    """
    filename = os.path.basename(filepath)
    date_str = filename.split('.')[0]
    date = pd.to_datetime(date_str, format='%Y%m%d')
    
    df = pd.read_csv(filepath)
    df['date'] = date
    
    # Filter for relevant columns to save memory if needed
    # df = df[['date', 'time', 'exchange', 'name', 'ltp', 'bid', 'ask', 'total_trade_qty']]
    
    return df

def identify_instruments(df):
    """
    Identifies CM, FUT1, FUT2 for each underlying.
    Returns a dictionary or dataframe mapping.
    """
    # Get all unique names
    names = df['name'].unique()
    
    # Group by underlying
    # Underlying name is usually the prefix of the future name
    # e.g. GAIL, GAIL25FEBFUT, GAIL25MARFUT
    
    # We can assume CM names are the base.
    cm_names = df[df['exchange'] == 'NSECM']['name'].unique()
    
    instruments = {}
    
    for cm in cm_names:
        # Find associated futures
        # Pattern: ^CM\d{2}[A-Z]{3}FUT
        # Actually the pattern in file is just CM... e.g. GAIL -> GAIL25FEBFUT
        
        # Simple startswith check might work, but need to be careful about similar names
        # e.g. TATASTEEL vs TATASTEELSL (if that existed)
        
        # Regex might be safer.
        # Future name starts with CM name
        
        candidates = [n for n in names if n.startswith(cm) and n != cm]
        
        # Sort candidates to find near and far.
        # Sorting by name might work if format is consistent: YYMON...
        # 25FEB comes before 25MAR.
        # But 25DEC comes after 25JAN? No, alphabetical.
        # JAN, FEB, MAR, APR, MAY, JUN, JUL, AUG, SEP, OCT, NOV, DEC
        # Alphabetical: APR, AUG, DEC, FEB, JAN, JUL, JUN, MAR, MAY, NOV, OCT, SEP
        # So alphabetical sort is NOT chronological.
        
        # We need to parse the expiry from the name.
        # Format: NAME + YY + MON + FUT
        # e.g. GAIL25FEBFUT
        
        futs = []
        for cand in candidates:
            # Extract month and year
            # Assuming last 3 chars before FUT are month
            # and 2 chars before that are year.
            match = re.search(r'(\d{2})([A-Z]{3})FUT$', cand)
            if match:
                yy = int(match.group(1))
                mon_str = match.group(2)
                try:
                    mon = datetime.strptime(mon_str, '%b').month
                    futs.append({
                        'name': cand,
                        'year': 2000 + yy,
                        'month': mon
                    })
                except ValueError:
                    pass
        
        # Sort futures chronologically
        futs.sort(key=lambda x: (x['year'], x['month']))
        
        if len(futs) >= 2:
            instruments[cm] = {
                'cm': cm,
                'fut1': futs[0]['name'],
                'fut2': futs[1]['name']
            }
        elif len(futs) == 1:
             instruments[cm] = {
                'cm': cm,
                'fut1': futs[0]['name'],
                'fut2': None
            }
            
    return instruments

def get_all_data_files():
    return sorted(glob.glob(os.path.join(DATA_DIR, "*.data.csv")))

if __name__ == "__main__":
    # Test run
    files = get_all_data_files()
    if files:
        print(f"Found {len(files)} files.")
        df = load_daily_data(files[0])
        print("Sample data loaded.")
        instruments = identify_instruments(df)
        print(f"Identified {len(instruments)} instrument sets.")
        for k, v in list(instruments.items())[:5]:
            print(f"{k}: {v}")
