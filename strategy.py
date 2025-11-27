import pandas as pd
import numpy as np

class MeanReversionStrategy:
    def __init__(self, lookback_window=750, entry_percentile=0.95, exit_percentile=0.50):
        """
        Dynamic threshold mean reversion strategy.
        
        Args:
            lookback_window: Number of periods to look back (default: 750 ~ 2 trading days)
            entry_percentile: Percentile for entry threshold (default: 0.95 for 95th/5th)
            exit_percentile: Percentile for exit (default: 0.50 for median)
        """
        self.lookback_window = lookback_window
        self.entry_percentile = entry_percentile
        self.exit_percentile = exit_percentile
        
    def generate_signals(self, spread_series):
        """
        Generates signals based on dynamic percentile thresholds.
        
        Entry: When spread exceeds the 95th percentile (short) or falls below 5th percentile (long)
               of the last `lookback_window` periods.
        Exit: When spread reverts to the median of the last `lookback_window` periods.
        
        Returns:
            positions: pd.Series with values {-1, 0, 1}
                1 = Long Spread (Buy Fut, Sell CM)
                -1 = Short Spread (Sell Fut, Buy CM)
                0 = No position
        """
        positions = pd.Series(0, index=spread_series.index, dtype=float)
        
        current_pos = 0
        
        # Convert to numpy for speed
        spread_vals = spread_series.values
        pos_vals = np.zeros(len(spread_vals))
        
        for i in range(self.lookback_window, len(spread_vals)):
            # Get lookback window
            window_data = spread_vals[i-self.lookback_window:i]
            
            # Skip if not enough valid data
            valid_data = window_data[~np.isnan(window_data)]
            if len(valid_data) < 30:  # Minimum data requirement
                pos_vals[i] = current_pos
                continue
            
            # Calculate dynamic thresholds from the lookback window
            upper_threshold = np.percentile(valid_data, self.entry_percentile * 100)
            lower_threshold = np.percentile(valid_data, (1 - self.entry_percentile) * 100)
            exit_level = np.percentile(valid_data, self.exit_percentile * 100)
            
            current_spread = spread_vals[i]
            
            if np.isnan(current_spread):
                pos_vals[i] = current_pos
                continue
            
            # Entry logic
            if current_pos == 0:
                if current_spread > upper_threshold:
                    current_pos = -1  # Short spread (expect reversion down)
                elif current_spread < lower_threshold:
                    current_pos = 1   # Long spread (expect reversion up)
            
            # Exit logic
            elif current_pos == 1:  # Long position
                if current_spread >= exit_level:
                    current_pos = 0
            
            elif current_pos == -1:  # Short position
                if current_spread <= exit_level:
                    current_pos = 0
            
            pos_vals[i] = current_pos
        
        positions = pd.Series(pos_vals, index=spread_series.index)
        return positions


