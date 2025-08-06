import asyncio
import logging
from typing import Tuple
import os
import sys
import pandas as pd
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

from database.connection import DatabaseConnection
from database.config import DatabaseConfig

class SignalGenerator:
    def __init__(self, 
                 atr_period: int = 14,
                 rolling_move: int = 30,
                 band_multiplier: float = 1.0,
                 use_vwap: bool = True):
        self.atr_period = atr_period
        self.rolling_move = rolling_move
        self.band_multiplier = band_multiplier
        self.use_vwap = use_vwap
        
    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        if len(df) < 100:
            return pd.DataFrame()
            
        df = df.copy()
        df['day'] = df['timestamp'].dt.date
        
        df['vwap'] = self._calculate_vwap(df)
        df['atr'] = self._calculate_atr(df)
        df['sigma_open'] = self._calculate_sigma_open(df)
        df = self._calculate_bands(df)
        
        return df
        
    @staticmethod
    def _calculate_vwap(df: pd.DataFrame) -> pd.Series:
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        return (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
        
    def _calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        high_low = df['high'] - df['low']
        high_close_prev = abs(df['high'] - df['close'].shift(1))
        low_close_prev = abs(df['low'] - df['close'].shift(1))
        true_range = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
        return true_range.rolling(window=self.atr_period).mean()
        
    def _calculate_sigma_open(self, df: pd.DataFrame) -> pd.Series:
        daily_data = df.groupby('day').agg({
            'open': 'first',
            'close': 'last'
        }).reset_index()
        
        daily_data['daily_move'] = abs(daily_data['close'] - daily_data['open']) / daily_data['open']
        daily_data['sigma_open'] = daily_data['daily_move'].rolling(window=self.rolling_move).std()
        
        day_to_sigma = dict(zip(daily_data['day'], daily_data['sigma_open']))
        return df['day'].map(day_to_sigma)
        
    def _calculate_bands(self, df: pd.DataFrame) -> pd.DataFrame:
        open_price = df.groupby('day')['open'].transform('first')
        prev_close_map = df['day'].map(df.groupby('day')['close'].last().shift(1).ffill())
        
        ub_base = pd.concat([open_price, prev_close_map], axis=1).max(axis=1)
        lb_base = pd.concat([open_price, prev_close_map], axis=1).min(axis=1)
        
        df['UB'] = ub_base * (1 + self.band_multiplier * df['sigma_open'])
        df['LB'] = lb_base * (1 - self.band_multiplier * df['sigma_open'])
        
        return df
        
    def get_latest_signal(self, df: pd.DataFrame) -> Tuple[int, str]:
        df_with_features = self.create_features(df)
        
        if df_with_features.empty:
            return 0, "insufficient_data"
            
        latest_row = df_with_features.iloc[-1]
        
        if pd.isna(latest_row.UB) or pd.isna(latest_row.LB):
            return 0, "insufficient_data"
            
        # Entry signals
        if latest_row.close > latest_row.UB:
            if not self.use_vwap or latest_row.close > latest_row.vwap:
                return 1, "band_cross_up"
        elif latest_row.close < latest_row.LB:
            if not self.use_vwap or latest_row.close < latest_row.vwap:
                return -1, "band_cross_down"
                
        return 0, "none"

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
                table_sql = f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    timestamp TIMESTAMPTZ NOT NULL,
                    symbol TEXT NOT NULL,
                    close DOUBLE PRECISION,
                    signal INTEGER,
                    reason TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (timestamp, symbol)
                );
                """
                await conn.execute(table_sql)
                logging.info(f"✅ {self.table_name} table ready")
        except Exception as e:
            logging.error(f"❌ Failed to create signal table: {e}")
            raise
            
    async def save_signal(self, timestamp, symbol, close, signal, reason):
        if signal == 0:
            return
            
        try:
            async with self.db_connection.pool.acquire() as conn:
                await conn.execute(f"""
                    INSERT INTO {self.table_name} (timestamp, symbol, close, signal, reason)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (timestamp, symbol) DO UPDATE SET
                        close = EXCLUDED.close, signal = EXCLUDED.signal, reason = EXCLUDED.reason;
                """, [timestamp, symbol, close, signal, reason])
            
            signal_type = "🟢 LONG" if signal == 1 else "🔴 SHORT"
            logging.info(f"🚨 {signal_type} SIGNAL: {close} ({reason})")
        except Exception as e:
            logging.error(f"❌ Failed to save signal: {e}")
            
    async def close(self):
        if self.db_connection.pool:
            await self.db_connection.close()