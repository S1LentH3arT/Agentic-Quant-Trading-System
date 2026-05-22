import numpy as np
import pandas as pd
from datetime import datetime

class SnowballAllocator:
    """
    Capital Allocation Engine for the 5k -> 20k Challenge.
    Implements a Core-Satellite leverage strategy designed for aggressive growth.
    """
    def __init__(self, initial_capital=5000):
        self.initial_capital = initial_capital
        self.current_assets = initial_capital
        self.risk_tolerance = 0.15  # 15% Max Drawdown before hard stop
        print(f"[{datetime.now()}] Snowball Allocator Initialized. Capital: {initial_capital}")

    def calculate_allocation(self, targets_df):
        """
        Calculates the exact funding distribution for the selected targets.
        """
        if targets_df.empty:
            return "No targets available for allocation."

        # 1. Selection: Pick the Top 2 targets by Beta * Gain
        targets_df['score'] = targets_df['beta'] * targets_df['gain']
        top_targets = targets_df.sort_values(by='score', ascending=False).head(2)

        # 2. Core-Satellite Split
        # Core (40%): Low leverage, stability
        # Satellite (60%): High leverage, the 'Snowball' growth engine
        core_budget = self.current_assets * 0.4
        satellite_budget = self.current_assets * 0.6

        allocation_plan = []

        for _, target in top_targets.iterrows():
            symbol = target['symbol']
            name = target['name']
            beta = target['beta']

            # Distribute budgets equally among top targets
            t_core = core_budget / len(top_targets)
            t_sat = satellite_budget / len(top_targets)

            # Calculate effective exposure (Leverage)
            # For Satellite, we assume a 1:5 leverage (via options or funding)
            effective_exposure = t_core + (t_sat * 5)

            allocation_plan.append({
                "Symbol": symbol,
                "Name": name,
                "Core_Allocation": round(t_core, 2),
                "Satellite_Allocation": round(t_sat, 2),
                "Effective_Exposure": round(effective_exposure, 2),
                "Leverage_Ratio": "1:5 (Satellite)",
                "Stop_Loss_Price": "Current_Price * 0.85" # Simplified
            })

        return pd.DataFrame(allocation_plan)

    def simulate_growth(self, target_return=4.0):
        """
        Calculates the compounding path to reach 20,000.
        """
        steps = []
        capital = self.initial_capital
        target = self.initial_capital * target_return

        while capital < target:
            # Assume 20% growth per successful 'swing' with 1:5 leverage
            # Return = Capital * (1 + (Growth * Leverage))
            growth_per_swing = 0.05 # 5% base move
            leverage = 5

            gain = capital * (growth_per_swing * leverage)
            capital += gain
            steps.append(round(capital, 2))

            if len(steps) > 100: break # Prevent infinite loop

        return steps

if __name__ == "__main__":
    # Mock target data from scanner.py
    mock_targets = pd.DataFrame({
        'symbol': ['000001', '600000'],
        'name': ['Target A', 'Target B'],
        'beta': [1.8, 2.1],
        'gain': [4.5, 5.2]
    })

    allocator = SnowballAllocator()
    plan = allocator.calculate_allocation(mock_targets)

    print("\n--- 💰 SNOWBALL ALLOCATION PLAN 💰 ---")
    print(plan)

    path = allocator.simulate_growth()
    print(f"\n--- 📈 COMPOUNDING PATH (Expected Swings to 20k) ---")
    print(f"Starting: {allocator.initial_capital} -> Final: {path[-1]}")
    print(f"Total swings required: {len(path)}")
