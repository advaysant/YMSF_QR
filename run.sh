#!/bin/bash

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install pandas matplotlib seaborn tqdm
else
    source venv/bin/activate
fi

# Run Analysis (Problem 1)
echo "Running Analysis..."
python3 analysis.py

# Run Simulation (Problem 2)
echo "Running Simulation..."
python3 backtester.py

# Rename results to include timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
cp output/Results.csv output/results.${TIMESTAMP}.csv

echo "Done. Results saved to output/results.${TIMESTAMP}.csv"
