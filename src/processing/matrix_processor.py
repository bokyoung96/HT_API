import logging
import warnings
from datetime import datetime
from services.time_service import TimeService
from typing import Dict, List

import pandas as pd
from models.dataclasses import OptionChainData, OptionData

warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', message='.*concatenation.*')
warnings.filterwarnings('ignore', message='.*empty entries.*')
pd.options.mode.chained_assignment = None


class OptionMatrixProcessor:
    def __init__(self, metrics: List[str], num_strikes: int = 10):
        self._metrics = metrics
        self._num_strikes = num_strikes
        self.matrices: Dict[str, pd.DataFrame] = self._create_matrices()
        self._last_print_time: datetime | None = None

    def _create_matrices(self) -> Dict[str, pd.DataFrame]:
        columns = self._generate_columns()
        return {metric: pd.DataFrame(columns=columns) for metric in self._metrics}

    def _generate_columns(self) -> List[str]:
        cols = []
        for side in ["C", "P"]:
            for i in range(self._num_strikes, 0, -1):
                cols.append(f"{side}_ITM{i}")
            cols.append(f"{side}_ATM")
            for i in range(1, self._num_strikes + 1):
                cols.append(f"{side}_OTM{i}")
        return cols

    def update(self, chain_data: OptionChainData) -> None:
        if not chain_data.calls and not chain_data.puts:
            return

        sorted_calls = sorted(chain_data.calls, key=lambda o: o.strike_price)
        sorted_puts = sorted(chain_data.puts, key=lambda o: o.strike_price)

        atm_calls = [o for o in sorted_calls if o.atm_class == "ATM"]
        atm_puts = [o for o in sorted_puts if o.atm_class == "ATM"]

        if not atm_calls or not atm_puts:
            logging.warning("ATM options not found in the data. Skipping update.")
            return

        new_rows = {
            metric: pd.Series(name=chain_data.timestamp, dtype=float)
            for metric in self._metrics
        }

        self._fill_row_by_atm_class(new_rows, sorted_calls, "C")
        self._fill_row_by_atm_class(new_rows, sorted_puts, "P")

        for metric in self._metrics:
            self.matrices[metric] = pd.concat(
                [self.matrices[metric], new_rows[metric].to_frame().T]
            )

        now = TimeService.now_kst_naive()
        if self._last_print_time is None or (now - self._last_print_time).total_seconds() >= 60:
            logging.info(
                f"📊 Option matrices updated for timestamp {chain_data.timestamp.isoformat()}."
            )
            print("\n--- Updated IV Matrix (Last 1 min) ---")
            print(self.matrices["iv"].tail())
            print("-" * 40)
            self._last_print_time = now

    def _fill_row_by_atm_class(
        self, new_rows: Dict[str, pd.Series], options: List[OptionData], side: str
    ):
        atm_options = [o for o in options if o.atm_class == "ATM"]
        if not atm_options:
            return

        atm_option = atm_options[0]

        for metric in self._metrics:
            new_rows[metric][f"{side}_ATM"] = getattr(atm_option, metric, None)

        itm_options = sorted(
            [o for o in options if o.atm_class == "ITM"],
            key=lambda o: o.strike_price,
            reverse=(side == "C"),
        )
        otm_options = sorted(
            [o for o in options if o.atm_class == "OTM"],
            key=lambda o: o.strike_price,
            reverse=(side == "C"),
        )

        for i, option in enumerate(itm_options[: self._num_strikes]):
            for metric in self._metrics:
                new_rows[metric][f"{side}_ITM{i+1}"] = getattr(option, metric, None)

        for i, option in enumerate(otm_options[: self._num_strikes]):
            for metric in self._metrics:
                new_rows[metric][f"{side}_OTM{i+1}"] = getattr(option, metric, None)
                
    def get_current_matrices(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        if not any(len(df) > 0 for df in self.matrices.values()):
            return {}
            
        result = {}
        for metric, df in self.matrices.items():
            if len(df) == 0:
                continue
                
            latest_row = df.iloc[-1]
            result[metric] = {
                "c": {},
                "p": {}
            }
            
            for col in df.columns:
                value = latest_row[col]
                if pd.notna(value):
                    if col.startswith("C_"):
                        key = col[2:].lower()
                        result[metric]["c"][key] = float(value)
                    elif col.startswith("P_"):
                        key = col[2:].lower()
                        result[metric]["p"][key] = float(value)
                        
        return result 