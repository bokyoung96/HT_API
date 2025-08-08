import asyncio
import logging
from typing import Dict, Any
import os
import sys
import pandas as pd
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

from database.connection import DatabaseConnection
from database.config import DatabaseConfig
from services.time_service import TimeService

class SignalGenerator:
    def __init__(self, 
                 atr_period: int = 10,
                 rolling_move: int = 5,
                 band_multiplier: float = 1.0,
                 use_vwap: bool = True,
                 observe_interval_minutes: int = 5):
        self.atr_period = atr_period
        self.rolling_move = rolling_move
        self.band_multiplier = band_multiplier
        self.use_vwap = use_vwap
        self.observe_interval_minutes = observe_interval_minutes
        
    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        if len(df) < 100:
            return pd.DataFrame()
            
        df = df.copy()
        df = df.sort_values('timestamp').reset_index(drop=True)

        df['day'] = df['timestamp'].dt.date
        
        unique_days = df['day'].nunique()
        date_range = f"{df['day'].min()} ~ {df['day'].max()}"
        logging.info(f"📊 Feature creation - Total records: {len(df)}, Unique days: {unique_days}, Date range: {date_range}")
        
        day_counts = df['day'].value_counts().sort_index()
        logging.debug(f"📅 Records per day: {dict(day_counts.tail(5))}")
        
        df['vwap'] = self._calculate_vwap(df)
        df['atr'] = self._calculate_atr(df)
        df['sigma_open'] = self._calculate_sigma_open(df)
        
        nan_count = df['sigma_open'].isna().sum()
        if nan_count > 0:
            logging.warning(f"⚠️ sigma_open has {nan_count} NaN values (need at least {self.rolling_move} days)")
            first_valid_idx = df['sigma_open'].first_valid_index()
            if first_valid_idx is not None:
                first_valid_date = df.loc[first_valid_idx, 'day']
                logging.info(f"📅 First valid sigma_open date: {first_valid_date}")
        
        df = self._calculate_bands(df)
        
        return df
        
    @staticmethod
    def _calculate_vwap(df: pd.DataFrame) -> pd.Series:
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        tpv = typical_price * df['volume']

        cumulative_tpv_daily = tpv.groupby(df['day']).cumsum()
        cumulative_volume_daily = df.groupby('day')['volume'].cumsum()
        
        return cumulative_tpv_daily / cumulative_volume_daily
        
    def _calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        high_low = df['high'] - df['low']
        high_close_prev = abs(df['high'] - df['close'].shift(1))
        low_close_prev = abs(df['low'] - df['close'].shift(1))
        true_range = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
        return true_range.rolling(window=self.atr_period).mean()
        
    def _calculate_sigma_open(self, df: pd.DataFrame) -> pd.Series:
        df['timestamp_local'] = df['timestamp']

        base_open_price = df.groupby('day')['open'].transform('first')            
        df['min_from_open'] = ((df['timestamp_local'] - df['timestamp_local'].dt.normalize()) / pd.Timedelta(minutes=1)) - 526  # 08:46
        df['move_open'] = (df['close'] / base_open_price - 1).abs()
        
        df['sigma_open'] = df.groupby('min_from_open')['move_open'].transform(
            lambda x: x.rolling(window=self.rolling_move, min_periods=max(self.rolling_move//2, 3)).mean().shift(1)
        )
        
        df['sigma_open'] = df.groupby('day')['sigma_open'].ffill().bfill()
        
        return df['sigma_open']
        
    def _calculate_bands(self, df: pd.DataFrame) -> pd.DataFrame:
        open_price = df.groupby('day')['open'].transform('first')
        prev_close_map = df['day'].map(df.groupby('day')['close'].last().shift(1).ffill())
        
        ub_base = pd.concat([open_price, prev_close_map], axis=1).max(axis=1)
        lb_base = pd.concat([open_price, prev_close_map], axis=1).min(axis=1)
        
        df['UB'] = ub_base * (1 + self.band_multiplier * df['sigma_open'])
        df['LB'] = lb_base * (1 - self.band_multiplier * df['sigma_open'])
        
        return df
        
    def get_latest_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        from datetime import datetime
        
        df_with_features = self.create_features(df)
        
        if df_with_features.empty:
            return {
                'monitor_signal': 0, 
                'trade_signal': 0, 
                'reason': 'insufficient_data',
                'ub': None, 'lb': None, 'current_price': None,
                'is_observe_time': False
            }
            
        valid_rows = df_with_features[df_with_features['UB'].notna() & df_with_features['LB'].notna()]
        
        if valid_rows.empty:
            unique_days = df['timestamp'].dt.date.nunique() if 'timestamp' in df else 0
            return {
                'monitor_signal': 0, 
                'trade_signal': 0, 
                'reason': f'insufficient_data_days_{unique_days}',
                'ub': None, 'lb': None, 'current_price': None,
                'is_observe_time': False
            }
            
        latest_row = valid_rows.iloc[-1]
        
        current_time = TimeService.now_kst_naive()
        is_observe_time = (current_time.minute % self.observe_interval_minutes == 0)
        
        monitor_signal = 0
        reason = "none"
        
        if latest_row.close > latest_row.UB:
            if not self.use_vwap or latest_row.close > latest_row.vwap:
                monitor_signal = 1
                reason = "band_cross_up"
        elif latest_row.close < latest_row.LB:
            if not self.use_vwap or latest_row.close < latest_row.vwap:
                monitor_signal = -1
                reason = "band_cross_down"
        
        trade_signal = monitor_signal if is_observe_time else 0
                
        return {
            'monitor_signal': monitor_signal,
            'trade_signal': trade_signal, 
            'reason': reason,
            'ub': float(latest_row.UB),
            'lb': float(latest_row.LB),
            'current_price': float(latest_row.close),
            'is_observe_time': is_observe_time,
            'atr': float(latest_row.atr),
            'move_open': float(latest_row.move_open),
            'sigma_open': float(latest_row.sigma_open),
            'vwap': float(latest_row.vwap),
            'min_from_open': float(latest_row.min_from_open)
        }

class SignalDatabase:
    def __init__(self, table_name: str = "dolpha1_signal"):
        self.table_name = table_name
        
        db_config_path = os.path.join(PROJECT_ROOT, "db_config.json")
        db_config = DatabaseConfig.from_json(config_path=db_config_path)
        self.db_connection = DatabaseConnection(db_config)
        
    async def initialize(self):
        if not self.db_connection.pool:
            await self.db_connection.initialize()
        await self._create_signal_table()
        
    async def _create_signal_table(self):
        try:
            async with self.db_connection.pool.acquire() as conn:
                # NOTE: Will be removed after testing
                await conn.execute(f"DROP TABLE IF EXISTS {self.table_name}")
                
                table_sql = f"""
                CREATE TABLE {self.table_name} (
                    timestamp TIMESTAMP NOT NULL,
                    symbol TEXT NOT NULL,
                    close DOUBLE PRECISION,
                    monitor_signal INTEGER,
                    trade_signal INTEGER,
                    reason TEXT,
                    ub DOUBLE PRECISION,
                    lb DOUBLE PRECISION,
                    atr DOUBLE PRECISION,
                    move_open DOUBLE PRECISION,
                    sigma_open DOUBLE PRECISION,
                    vwap DOUBLE PRECISION,
                    min_from_open DOUBLE PRECISION,
                    created_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (timestamp, symbol)
                );
                """
                await conn.execute(table_sql)
                logging.info(f"✅ {self.table_name} table recreated with new schema")
        except Exception as e:
            logging.error(f"❌ Failed to create signal table: {e}")
            raise
            
    async def save_signal(self, timestamp, symbol, signal_data: Dict[str, Any]):
        try:
            async with self.db_connection.pool.acquire() as conn:
                await conn.execute(f"""
                    INSERT INTO {self.table_name} (
                        timestamp, symbol, close, monitor_signal, trade_signal, 
                        reason, ub, lb, atr, move_open, sigma_open, vwap, min_from_open
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    ON CONFLICT (timestamp, symbol) DO UPDATE SET
                        close = EXCLUDED.close, 
                        monitor_signal = EXCLUDED.monitor_signal, 
                        trade_signal = EXCLUDED.trade_signal, 
                        reason = EXCLUDED.reason, 
                        ub = EXCLUDED.ub, 
                        lb = EXCLUDED.lb,
                        atr = EXCLUDED.atr,
                        move_open = EXCLUDED.move_open,
                        sigma_open = EXCLUDED.sigma_open,
                        vwap = EXCLUDED.vwap,
                        min_from_open = EXCLUDED.min_from_open;
                """, 
                    timestamp, symbol, signal_data['current_price'], 
                    signal_data['monitor_signal'], signal_data['trade_signal'], 
                    signal_data['reason'], signal_data['ub'], signal_data['lb'],
                    signal_data['atr'], signal_data['move_open'], 
                    signal_data['sigma_open'], signal_data['vwap'],
                    signal_data['min_from_open']
                )
            
            logging.debug(f"💾 Signal saved: Monitor={signal_data['monitor_signal']}, Trade={signal_data['trade_signal']} at {signal_data['current_price']:.2f}")
        except Exception as e:
            logging.error(f"❌ Failed to save signal: {e}")
            
    async def close(self):
        if self.db_connection.pool:
            await self.db_connection.close()