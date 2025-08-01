import logging
import asyncio
from enum import Enum
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta


class TimeFrame(Enum):
    """지원하는 시간 프레임"""
    MIN_1 = "1m"
    MIN_5 = "5m" 
    MIN_15 = "15m"
    MIN_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"


@dataclass
class Candle:
    """
    OHLCV 캔들 데이터 구조
    
    Attributes:
        symbol: 종목코드 (예: "005930", "101W09")
        timeframe: 시간 프레임 (1m, 5m, 15m 등)
        timestamp: 캔들 시작 시간 (정확한 분봉 구간 시작점)
        open: 시가 (해당 구간 첫 번째 가격)
        high: 고가 (해당 구간 최고 가격)
        low: 저가 (해당 구간 최저 가격)
        close: 종가 (해당 구간 마지막 가격, 실시간 업데이트)
        volume: 거래량 (누적 거래량)
    """
    symbol: str
    timeframe: TimeFrame
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    
    def __str__(self) -> str:
        """캔들을 읽기 쉬운 형태로 출력"""
        return (f"[{self.symbol}] {self.timeframe.value} "
                f"{self.timestamp.strftime('%H:%M')} "
                f"O:{self.open:.2f} H:{self.high:.2f} L:{self.low:.2f} "
                f"C:{self.close:.2f} V:{self.volume}")
    
    def to_dict(self) -> Dict[str, Any]:
        """캔들을 딕셔너리로 변환"""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe.value,
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume
        }


class ICandleSubscriber(ABC):
    """캔들 데이터를 수신할 구독자 인터페이스"""
    
    @abstractmethod
    async def on_candle_completed(self, candle: Candle) -> None:
        """완성된 캔들을 받을 때 호출"""
        pass
    
    async def on_candle_updated(self, candle: Candle) -> None:
        """진행중인 캔들이 업데이트될 때 호출 (선택사항)"""
        pass


class CandleAggregator:
    """
    틱 데이터를 OHLCV 캔들로 집계하는 핵심 클래스
    
    동작 원리:
    1. 틱 데이터가 들어오면 현재 시간 기준으로 적절한 캔들 구간 계산
    2. 해당 구간의 캔들이 없으면 새로 생성 (Open = 현재가)
    3. 기존 캔들이 있으면 High/Low/Close 업데이트
    4. 새로운 시간 구간에 진입하면 이전 캔들을 완성으로 처리
    """
    
    def __init__(self, timeframe: TimeFrame, subscribers: List[ICandleSubscriber] = None):
        """
        Args:
            timeframe: 집계할 시간 프레임
            subscribers: 캔들 완성 시 알림받을 구독자들
        """
        self.timeframe = timeframe
        self.subscribers = subscribers or []
        self.current_candles: Dict[str, Candle] = {}  # symbol -> 현재 진행중인 캔들
        
        logging.info(f"📊 CandleAggregator initialized for {timeframe.value}")
    
    def add_subscriber(self, subscriber: ICandleSubscriber) -> None:
        """캔들 구독자 추가"""
        self.subscribers.append(subscriber)
        logging.info(f"Added candle subscriber: {subscriber.__class__.__name__}")
    
    def _get_candle_start_time(self, timestamp: datetime) -> datetime:
        """
        주어진 시간을 기준으로 해당 캔들의 정확한 시작 시간 계산
        
        예시:
        - 1분봉: 09:46:37 → 09:46:00
        - 5분봉: 09:46:37 → 09:45:00 (5분 단위로 정렬)
        - 15분봉: 09:46:37 → 09:45:00 (15분 단위로 정렬)
        - 1시간봉: 09:46:37 → 09:00:00
        """
        if self.timeframe == TimeFrame.MIN_1:
            return timestamp.replace(second=0, microsecond=0)
        
        elif self.timeframe == TimeFrame.MIN_5:
            # 5분 단위로 정렬: 0, 5, 10, 15, ... 분
            minute = (timestamp.minute // 5) * 5
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        
        elif self.timeframe == TimeFrame.MIN_15:
            # 15분 단위로 정렬: 0, 15, 30, 45분
            minute = (timestamp.minute // 15) * 15
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        
        elif self.timeframe == TimeFrame.MIN_30:
            # 30분 단위로 정렬: 0, 30분
            minute = (timestamp.minute // 30) * 30
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        
        elif self.timeframe == TimeFrame.HOUR_1:
            # 1시간 단위로 정렬
            return timestamp.replace(minute=0, second=0, microsecond=0)
        
        elif self.timeframe == TimeFrame.HOUR_4:
            # 4시간 단위로 정렬: 0, 4, 8, 12, 16, 20시
            hour = (timestamp.hour // 4) * 4
            return timestamp.replace(hour=hour, minute=0, second=0, microsecond=0)
        
        elif self.timeframe == TimeFrame.DAY_1:
            # 일봉은 장 시작 시간 (09:00)으로 설정
            return timestamp.replace(hour=9, minute=0, second=0, microsecond=0)
        
        else:
            # 기본값: 초/마이크로초만 0으로
            return timestamp.replace(second=0, microsecond=0)
    
    async def process_tick(self, tick_data: Dict[str, Any]) -> Optional[Candle]:
        """
        틱 데이터를 처리하여 캔들 집계
        
        Args:
            tick_data: 웹소켓에서 받은 틱 데이터
                      {"code": "101W09", "current_price": 427.30, "volume": 150, ...}
        
        Returns:
            완성된 캔들 (새로운 시간 구간 진입시) 또는 None
        """
        # 틱 데이터에서 필요한 정보 추출
        symbol = tick_data.get("code", "UNKNOWN")
        price = tick_data.get("current_price", tick_data.get("price", 0.0))
        volume = tick_data.get("volume", 0)
        
        # 유효하지 않은 가격 데이터는 무시
        if price <= 0:
            logging.debug(f"Invalid price data for {symbol}: {price}")
            return None
        
        # 현재 시간 기준으로 캔들 시작 시간 계산
        now = datetime.now()
        candle_start = self._get_candle_start_time(now)
        
        # 기존 캔들 확인
        current_candle = self.current_candles.get(symbol)
        completed_candle = None
        
        # 새로운 시간 구간 진입 체크
        if current_candle and current_candle.timestamp != candle_start:
            # 이전 캔들 완성 처리
            completed_candle = current_candle
            logging.info(f"🕯️ Candle completed: {completed_candle}")
            
            # 구독자들에게 완성된 캔들 알림
            for subscriber in self.subscribers:
                try:
                    await subscriber.on_candle_completed(completed_candle)
                except Exception as e:
                    logging.error(f"Error notifying subscriber {subscriber}: {e}")
        
        # 새 캔들 생성 또는 기존 캔들 업데이트
        if (symbol not in self.current_candles or 
            (current_candle and current_candle.timestamp != candle_start)):
            
            # 새 캔들 생성
            self.current_candles[symbol] = Candle(
                symbol=symbol,
                timeframe=self.timeframe,
                timestamp=candle_start,
                open=price,      # 시가: 첫 번째 가격
                high=price,      # 고가: 초기값은 첫 번째 가격
                low=price,       # 저가: 초기값은 첫 번째 가격
                close=price,     # 종가: 실시간으로 업데이트되는 마지막 가격
                volume=volume    # 거래량
            )
            logging.debug(f"🆕 New candle started for {symbol} at {candle_start}")
            
        else:
            # 기존 캔들 업데이트
            candle = self.current_candles[symbol]
            
            # 고가/저가 업데이트
            candle.high = max(candle.high, price)
            candle.low = min(candle.low, price)
            
            # 종가는 항상 최신 가격으로 업데이트
            candle.close = price
            
            # 거래량 업데이트 (누적 방식 - 최대값 사용)
            candle.volume = max(candle.volume, volume)
            
            logging.debug(f"🔄 Candle updated for {symbol}: {price}")
        
        # 구독자들에게 캔들 업데이트 알림
        if symbol in self.current_candles:
            for subscriber in self.subscribers:
                try:
                    await subscriber.on_candle_updated(self.current_candles[symbol])
                except Exception as e:
                    logging.debug(f"Error notifying subscriber update {subscriber}: {e}")
        
        return completed_candle
    
    def get_current_candle(self, symbol: str) -> Optional[Candle]:
        """특정 종목의 현재 진행중인 캔들 조회"""
        return self.current_candles.get(symbol)
    
    def get_all_current_candles(self) -> Dict[str, Candle]:
        """모든 진행중인 캔들 조회"""
        return self.current_candles.copy()
    
    def get_candle_progress(self, symbol: str) -> float:
        """
        현재 캔들의 진행률 계산 (0.0 ~ 1.0)
        
        Returns:
            0.0: 캔들 시작
            1.0: 캔들 완성 직전
        """
        candle = self.current_candles.get(symbol)
        if not candle:
            return 0.0
        
        now = datetime.now()
        candle_start = candle.timestamp
        
        # 다음 캔들 시작 시간 계산
        if self.timeframe == TimeFrame.MIN_1:
            next_start = candle_start + timedelta(minutes=1)
        elif self.timeframe == TimeFrame.MIN_5:
            next_start = candle_start + timedelta(minutes=5)
        elif self.timeframe == TimeFrame.MIN_15:
            next_start = candle_start + timedelta(minutes=15)
        elif self.timeframe == TimeFrame.MIN_30:
            next_start = candle_start + timedelta(minutes=30)
        elif self.timeframe == TimeFrame.HOUR_1:
            next_start = candle_start + timedelta(hours=1)
        elif self.timeframe == TimeFrame.HOUR_4:
            next_start = candle_start + timedelta(hours=4)
        elif self.timeframe == TimeFrame.DAY_1:
            next_start = candle_start + timedelta(days=1)
        else:
            next_start = candle_start + timedelta(minutes=1)
        
        total_duration = (next_start - candle_start).total_seconds()
        elapsed_duration = (now - candle_start).total_seconds()
        
        return min(elapsed_duration / total_duration, 1.0)


class CandleManager:
    """
    여러 시간 프레임의 캔들을 동시에 관리하는 매니저 클래스
    
    사용법:
        manager = CandleManager()
        manager.add_timeframe(TimeFrame.MIN_1, [subscriber1])
        manager.add_timeframe(TimeFrame.MIN_5, [subscriber2])
        
        # 틱 데이터 처리
        await manager.process_tick(tick_data)
    """
    
    def __init__(self):
        self.aggregators: Dict[TimeFrame, CandleAggregator] = {}
        
    def add_timeframe(self, timeframe: TimeFrame, subscribers: List[ICandleSubscriber] = None):
        """새로운 시간 프레임 추가"""
        if timeframe not in self.aggregators:
            self.aggregators[timeframe] = CandleAggregator(timeframe, subscribers)
            logging.info(f"Added timeframe {timeframe.value} to CandleManager")
        else:
            # 기존 시간 프레임에 구독자 추가
            if subscribers:
                for subscriber in subscribers:
                    self.aggregators[timeframe].add_subscriber(subscriber)
    
    def add_subscriber_to_timeframe(self, timeframe: TimeFrame, subscriber: ICandleSubscriber):
        """특정 시간 프레임에 구독자 추가"""
        if timeframe in self.aggregators:
            self.aggregators[timeframe].add_subscriber(subscriber)
        else:
            logging.warning(f"Timeframe {timeframe.value} not found in manager")
    
    async def process_tick(self, tick_data: Dict[str, Any]) -> Dict[TimeFrame, Optional[Candle]]:
        """
        모든 시간 프레임에 틱 데이터 전송
        
        Returns:
            각 시간 프레임별로 완성된 캔들 (없으면 None)
        """
        completed_candles = {}
        
        for timeframe, aggregator in self.aggregators.items():
            try:
                completed_candle = await aggregator.process_tick(tick_data)
                completed_candles[timeframe] = completed_candle
            except Exception as e:
                logging.error(f"Error processing tick for {timeframe.value}: {e}")
                completed_candles[timeframe] = None
        
        return completed_candles
    
    def get_current_candle(self, timeframe: TimeFrame, symbol: str) -> Optional[Candle]:
        """특정 시간 프레임의 현재 캔들 조회"""
        if timeframe in self.aggregators:
            return self.aggregators[timeframe].get_current_candle(symbol)
        return None
    
    def get_all_current_candles(self, timeframe: TimeFrame) -> Dict[str, Candle]:
        """특정 시간 프레임의 모든 현재 캔들 조회"""
        if timeframe in self.aggregators:
            return self.aggregators[timeframe].get_all_current_candles()
        return {}
    
    def get_candle_progress(self, timeframe: TimeFrame, symbol: str) -> float:
        """특정 시간 프레임의 캔들 진행률 조회"""
        if timeframe in self.aggregators:
            return self.aggregators[timeframe].get_candle_progress(symbol)
        return 0.0


# 예시 구독자 구현
class LoggingCandleSubscriber(ICandleSubscriber):
    """캔들을 로그로 출력하는 구독자"""
    
    def __init__(self, name: str = "CandleLogger"):
        self.name = name
    
    async def on_candle_completed(self, candle: Candle) -> None:
        """완성된 캔들 로깅"""
        logging.info(f"🕯️ {self.name}: {candle}")
    
    async def on_candle_updated(self, candle: Candle) -> None:
        """진행중인 캔들 업데이트 로깅 (디버그 레벨)"""
        logging.debug(f"🔄 {self.name}: {candle}")


class FileCandleSubscriber(ICandleSubscriber):
    """캔들을 파일로 저장하는 구독자"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        
    async def on_candle_completed(self, candle: Candle) -> None:
        """완성된 캔들을 파일에 저장"""
        try:
            with open(self.file_path, 'a', encoding='utf-8') as f:
                f.write(f"{candle.to_dict()}\n")
        except Exception as e:
            logging.error(f"Failed to write candle to file: {e}")


if __name__ == "__main__":
    """
    테스트 및 사용 예시
    """
    import asyncio
    
    async def test_candle_aggregation():
        # 로깅 설정
        logging.basicConfig(level=logging.INFO, 
                          format='%(asctime)s [%(levelname)s] %(message)s')
        
        # 구독자 생성
        logger = LoggingCandleSubscriber("TestLogger")
        
        # 캔들 매니저 생성 및 설정
        manager = CandleManager()
        manager.add_timeframe(TimeFrame.MIN_1, [logger])
        manager.add_timeframe(TimeFrame.MIN_5, [logger])
        
        # 가상 틱 데이터로 테스트
        test_ticks = [
            {"code": "TEST001", "current_price": 100.0, "volume": 100},
            {"code": "TEST001", "current_price": 101.5, "volume": 150},
            {"code": "TEST001", "current_price": 99.8, "volume": 200},
            {"code": "TEST001", "current_price": 102.0, "volume": 250},
        ]
        
        print("=== 캔들 집계 테스트 시작 ===")
        
        for i, tick in enumerate(test_ticks):
            print(f"\nTick {i+1}: {tick}")
            completed_candles = await manager.process_tick(tick)
            
            # 현재 진행중인 캔들 상태 출력
            current_1m = manager.get_current_candle(TimeFrame.MIN_1, "TEST001")
            if current_1m:
                progress = manager.get_candle_progress(TimeFrame.MIN_1, "TEST001")
                print(f"Current 1m candle: {current_1m} (Progress: {progress:.2%})")
        
        print("\n=== 테스트 완료 ===")
    
    # 테스트 실행
    # asyncio.run(test_candle_aggregation()) 