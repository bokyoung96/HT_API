# HT_API - 한국투자증권 API 트레이딩 시스템

## 📋 프로젝트 개요

HT_API는 한국투자증권(KIS) API를 활용한 **실시간 트레이딩 데이터 수집 및 처리 시스템**입니다. 주식, 선물, 옵션 데이터를 REST API와 WebSocket을 통해 수집하고, 실시간으로 처리하여 트레이딩 전략에 활용할 수 있는 기반을 제공합니다.

## 🏗️ 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        HT_API System                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │   src/      │    │    wsc/     │    │  postman/   │        │
│  │ (REST API)  │    │(WebSocket)  │    │ (API Test)  │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

### 📁 디렉토리 구조

```
HT_API/
├── src/                    # REST API 기반 데이터 수집
│   ├── main.py            # 애플리케이션 진입점
│   ├── base.py            # 기본 설정 및 인증
│   ├── orchestration.py   # 전체 시스템 조율
│   ├── protocols.py       # 인터페이스 정의
│   ├── utils.py           # 유틸리티 함수
│   ├── config.json        # 설정 파일
│   ├── core/              # 핵심 기능
│   │   ├── feed.py        # 데이터 피드 관리
│   │   ├── polling.py     # 폴링 로직
│   │   └── subscription.py # 구독 관리
│   ├── fetchers/          # 데이터 수집기
│   │   ├── factory.py     # Fetcher 팩토리
│   │   ├── base_fetcher.py # 기본 Fetcher
│   │   ├── stock_fetcher.py # 주식 데이터 수집
│   │   ├── deriv_fetcher.py # 선물 데이터 수집
│   │   └── option_chain_fetcher.py # 옵션 체인 수집
│   ├── processing/        # 데이터 처리
│   │   ├── processors.py  # 데이터 프로세서
│   │   └── matrix_processor.py # 옵션 매트릭스 처리
│   └── models/            # 데이터 모델
│       ├── dataclasses.py # 데이터 클래스
│       └── enums.py       # 열거형 정의
├── wsc/                   # WebSocket 기반 실시간 처리
│   ├── feed.py           # 실시간 데이터 피드
│   ├── candle.py         # 캔들 데이터 처리
│   ├── base.py           # WebSocket 기본 설정
│   ├── strategy.py       # 트레이딩 전략
│   ├── order.py          # 주문 처리
│   ├── tools.py          # WebSocket 도구
│   └── config.json       # WebSocket 설정
└── postman/              # API 테스트 컬렉션
```

## 🔄 데이터 흐름

### 1. REST API 기반 데이터 수집 (src/)

```
User Request → main.py → DataFeedBuilder → DataFeedOrchestrator
                                                    ↓
FetcherFactory → [StockFetcher, DerivFetcher, OptionChainFetcher]
                                                    ↓
REST API Calls → DataProcessor → MatrixProcessor → Output
```

### 2. WebSocket 기반 실시간 처리 (wsc/)

```
WebSocket Connection → KISDataFeed → Handlers → Queue
                                                    ↓
DataProcessor → CandleAggregator → Subscribers → Output
```

## 📊 핵심 컴포넌트 상세 분석

### 1. 진입점 (main.py)

**역할**: 애플리케이션의 시작점

```python
async def main():
    config = KISConfig("config.json")
    auth = KISAuth(config, client)
    
    builder = (
        DataFeedBuilder(config, auth, client)
        .add_stock("005930", timeframe=1, name="Samsung Electronics")
        .add_deriv("101W09", timeframe=1, name="KOSPI200 Futures")
        .add_option_chain(maturity="202509", name="KOSPI200 Monthly Options")
    )
    
    orchestrator = builder.build()
    await orchestrator.start()
```

**주요 기능**:
- 설정 파일 로드
- 인증 토큰 관리
- 데이터 구독 설정
- 시스템 오케스트레이션 시작

### 2. 기본 설정 및 인증 (base.py)

#### KISConfig 클래스
```python
@dataclass
class KISConfig:
    app_key: str
    app_secret: str
    base_url: str
    account_number: str
    polling_interval: int
    stock_minute_tr_id: str
    deriv_minute_tr_id: str
    option_chain_tr_id: str
    config_dir: str
```

**역할**: 한국투자증권 API 설정 관리
- API 키 및 시크릿 관리
- 계좌번호 설정
- 폴링 간격 설정
- TR ID 설정 (거래 요청 ID)

#### KISAuth 클래스
```python
class KISAuth:
    def __init__(self, config: KISConfig, client: httpx.AsyncClient):
        self._config = config
        self._client = client
        self._token_file = os.path.join(config.config_dir, "access_token.json")
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None
```

**역할**: OAuth2 토큰 관리
- 액세스 토큰 발급 및 갱신
- 토큰 만료 시간 관리
- 토큰 파일 저장/로드
- 자동 토큰 갱신 (만료 10분 전)

### 3. 시스템 오케스트레이션 (orchestration.py)

#### DataFeedOrchestrator 클래스
```python
class DataFeedOrchestrator:
    def __init__(self, subscription_manager, fetcher_factory, config, auth, client):
        self._subscription_manager = subscription_manager
        self._fetcher_factory = fetcher_factory
        self._config = config
        self._auth = auth
        self._client = client
```

**역할**: 전체 데이터 수집 시스템 조율
- 구독 관리자와 연동
- Fetcher 팩토리를 통한 데이터 수집기 생성
- 공유 큐를 통한 데이터 전달
- 비동기 태스크 관리

#### DataFeedBuilder 클래스
```python
class DataFeedBuilder:
    def add_stock(self, symbol: str, timeframe: int = 1, name: Optional[str] = None):
        self._subscription_manager.add_subscription(
            SubscriptionConfig(DataType.S_CANDLE, symbol, timeframe, name)
        )
        return self
```

**역할**: Fluent API를 통한 구독 설정
- 주식 데이터 구독 추가
- 선물 데이터 구독 추가
- 옵션 체인 구독 추가
- 체이닝 방식의 API 제공

### 4. 데이터 모델 (models/)

#### CandleData 클래스
```python
@dataclass
class CandleData:
    symbol: str
    timestamp: datetime
    timeframe: int
    open: float
    high: float
    low: float
    close: float
    volume: int
    data_type: str
```

**역할**: OHLCV 캔들 데이터 구조 정의
- 종목코드, 타임스탬프, 시간프레임
- 시가, 고가, 저가, 종가, 거래량
- 딕셔너리 변환 메서드 제공

#### OptionData 클래스
```python
@dataclass
class OptionData:
    symbol: str
    atm_class: str  # ITM, ATM, OTM
    strike_price: float
    price: float
    iv: float      # 내재변동성
    delta: float   # 델타
    gamma: float   # 감마
    vega: float    # 베가
    theta: float   # 세타
    rho: float     # 로우
    volume: int
    open_interest: int
```

**역할**: 옵션 데이터 구조 정의
- 행권가, 현재가, 거래량, 미결제약정
- 그릭스 옵션 지표 (델타, 감마, 베가, 세타, 로우)
- 내재변동성 (IV)

#### OptionChainData 클래스
```python
@dataclass
class OptionChainData:
    timestamp: datetime
    underlying_symbol: str
    underlying_price: float
    calls: List[OptionData]
    puts: List[OptionData]
    data_type: str = "option_chain"
```

**역할**: 옵션 체인 데이터 구조 정의
- 기초자산 정보 (심볼, 가격)
- 콜 옵션 리스트
- 풋 옵션 리스트
- 전체 옵션 체인 데이터 관리

### 5. 데이터 수집기 (fetchers/)

#### FetcherFactory 클래스
```python
class FetcherFactory(FetcherFactoryProtocol):
    def __init__(self):
        self._registry = FetcherRegistry()
        self._register_default_fetchers()
    
    def _register_default_fetchers(self):
        self._registry.register(DataType.S_CANDLE, StockPriceFetcher)
        self._registry.register(DataType.D_CANDLE, DerivPriceFetcher)
        self._registry.register(DataType.O_CHAIN, OptionChainFetcher)
```

**역할**: 데이터 수집기 팩토리 패턴 구현
- 데이터 타입별 Fetcher 등록
- 설정에 따른 적절한 Fetcher 생성
- 확장 가능한 구조 제공

#### StockPriceFetcher 클래스
```python
class StockPriceFetcher(PriceFetcher):
    def __init__(self, queue, config, auth, client, symbol, timeframe):
        super().__init__(queue, config, auth, client, symbol, timeframe)
        self._tr_id = config.stock_minute_tr_id
```

**역할**: 주식 분봉 데이터 수집
- 한국투자증권 주식 API 호출
- 분봉 데이터 파싱 및 변환
- 큐를 통한 데이터 전달

#### DerivPriceFetcher 클래스
```python
class DerivPriceFetcher(PriceFetcher):
    def __init__(self, queue, config, auth, client, symbol, timeframe):
        super().__init__(queue, config, auth, client, symbol, timeframe)
        self._tr_id = config.deriv_minute_tr_id
```

**역할**: 선물 분봉 데이터 수집
- 한국투자증권 선물 API 호출
- 선물 특화 데이터 처리
- 시간프레임별 데이터 집계

#### OptionChainFetcher 클래스
```python
class OptionChainFetcher(PriceFetcher):
    def __init__(self, queue, config, auth, client, symbol, timeframe, 
                 maturity, underlying_asset_type):
        super().__init__(queue, config, auth, client, symbol, timeframe)
        self._tr_id = config.option_chain_tr_id
        self._maturity = maturity
        self._underlying_asset_type = underlying_asset_type
```

**역할**: 옵션 체인 데이터 수집
- 만기별 옵션 체인 조회
- 콜/풋 옵션 데이터 수집
- 그릭스 지표 계산

### 6. 데이터 처리 (processing/)

#### DataProcessor 클래스
```python
class DataProcessor(DataProcessorProtocol):
    def __init__(self, queue: asyncio.Queue):
        self._queue = queue
        self._processed_count = 0
        self._matrix_processor = OptionMatrixProcessor(
            metrics=["iv", "delta", "gamma", "theta", "vega", 
                    "price", "volume", "open_interest"],
            num_strikes=10,
        )
```

**역할**: 데이터 처리 파이프라인
- 큐에서 데이터 수신
- 데이터 타입별 분기 처리
- 옵션 매트릭스 업데이트
- 처리 카운트 관리

#### CandleProcessor 클래스
```python
class CandleProcessor:
    def __init__(self, symbol: str, timeframe: int, queue: asyncio.Queue):
        self.symbol = symbol
        self.timeframe = timeframe
        self.queue = queue
        self._last_processed_time: Optional[str] = None
```

**역할**: 캔들 데이터 중복 처리 방지
- 시간 기반 중복 체크
- 첫 실행 처리 로직
- 데이터 변환 및 큐 전송

### 7. WebSocket 실시간 처리 (wsc/)

#### KISDataFeed 클래스
```python
class KISDataFeed(IDataFeed):
    def __init__(self, config: KISConfig, auth: KISAuth, handlers: List[Handler]):
        self._config = config
        self._auth = auth
        self._handlers = handlers
        self._connected = False
        self._message_count = 0
```

**역할**: WebSocket 실시간 데이터 피드
- WebSocket 연결 관리
- 구독 요청 전송
- 실시간 메시지 처리
- 핸들러를 통한 데이터 분배

#### CandleAggregator 클래스
```python
class CandleAggregator:
    def __init__(self, timeframe: TimeFrame, subscribers: List[ICandleSubscriber] = None):
        self.timeframe = timeframe
        self.subscribers = subscribers or []
        self.current_candles: Dict[str, Candle] = {}
```

**역할**: 실시간 캔들 집계
- 틱 데이터를 OHLCV 캔들로 변환
- 시간프레임별 정확한 구간 계산
- 구독자 패턴을 통한 알림
- 진행중인 캔들 관리

#### Handler 클래스들
```python
class StockPriceHandler(Handler):
    async def handle_message(self, msg: str):
        # 주식 체결가 처리
        
class StockQuoteHandler(Handler):
    async def handle_message(self, msg: str):
        # 주식 호가 처리
        
class FuturesPriceHandler(Handler):
    async def handle_message(self, msg: str):
        # 선물 체결가 처리
        
class FuturesQuoteHandler(Handler):
    async def handle_message(self, msg: str):
        # 선물 호가 처리
```

**역할**: 데이터 타입별 메시지 처리
- WebSocket 메시지 파싱
- 데이터 구조화
- 큐를 통한 전달

## 🔧 설정 및 환경

### config.json 구조
```json
{
  "app_key": "your_app_key",
  "app_secret": "your_app_secret",
  "base_url": "https://openapi.koreainvestment.com:9443",
  "account_no": "your_account_number",
  "account_no_sub": "01",
  "polling_interval": 2,
  "tr_id": {
    "stock_minute": "FHKST01010400",
    "deriv_minute": "FHKIF01010400",
    "option_chain": "FHPIF05030100"
  }
}
```

### 환경 요구사항
- Python 3.8+
- httpx (HTTP 클라이언트)
- asyncio (비동기 처리)
- 한국투자증권 API 계정

## 🚀 사용법

### 1. REST API 기반 데이터 수집
```python
# main.py 실행
python src/main.py
```

### 2. WebSocket 기반 실시간 처리
```python
# wsc/ 디렉토리에서 실행
python feed.py
```

### 3. 설정 변경
- `config.json` 파일에서 API 키 및 계좌 정보 설정
- `polling_interval`로 데이터 수집 주기 조정
- 구독할 종목 및 시간프레임 설정

## 📈 데이터 타입

### 1. 주식 데이터 (S_CANDLE)
- 종목코드, 시간프레임
- OHLCV 캔들 데이터
- 실시간 가격 정보

### 2. 선물 데이터 (D_CANDLE)
- 선물코드, 시간프레임
- OHLCV 캔들 데이터
- 선물 특화 정보

### 3. 옵션 체인 데이터 (O_CHAIN)
- 만기, 기초자산
- 콜/풋 옵션 리스트
- 그릭스 지표 (델타, 감마, 베가, 세타, 로우)
- 내재변동성 (IV)

## 🔄 실시간 처리 흐름

### WebSocket 기반 실시간 처리
```
1. WebSocket 연결 → KISDataFeed
2. 구독 요청 전송 → Handlers
3. 실시간 메시지 수신 → CandleAggregator
4. 캔들 집계 → Subscribers
5. 로깅/파일저장 → Output
```

### REST API 기반 폴링 처리
```
1. 설정 로드 → KISConfig
2. 인증 토큰 발급 → KISAuth
3. 데이터 수집 → Fetchers
4. 데이터 처리 → Processors
5. 매트릭스 업데이트 → MatrixProcessor
```

## 🛠️ 확장성

### 1. 새로운 데이터 타입 추가
- `models/enums.py`에 새로운 DataType 추가
- `fetchers/`에 새로운 Fetcher 구현
- `FetcherFactory`에 등록

### 2. 새로운 처리 로직 추가
- `processing/`에 새로운 Processor 구현
- `DataProcessor`에 처리 로직 추가

### 3. 새로운 출력 방식 추가
- `ICandleSubscriber` 인터페이스 구현
- `CandleAggregator`에 구독자 추가

## 🔍 모니터링 및 로깅

### 로그 파일
- `kis_api.log`: API 호출 및 오류 로그
- 실시간 처리 상태 모니터링
- 데이터 처리 카운트 추적

### 성능 지표
- 메시지 처리 수
- 데이터 수집 성공률
- API 응답 시간
- 캔들 집계 정확도

## ⚠️ 주의사항

1. **API 제한**: 한국투자증권 API 호출 제한 준수
2. **토큰 관리**: 액세스 토큰 자동 갱신 확인
3. **장 시간**: 주식/선물/옵션 장 시간 확인
4. **에러 처리**: 네트워크 오류 및 API 오류 처리
5. **메모리 관리**: 대용량 데이터 처리 시 메모리 사용량 모니터링

## 📚 참고 자료

- [한국투자증권 Open API 가이드](https://securities.koreainvestment.com/apiservice/intro)
- [Python asyncio 문서](https://docs.python.org/3/library/asyncio.html)
- [httpx 문서](https://www.python-httpx.org/)

---

이 문서는 HT_API 시스템의 전체 구조와 각 컴포넌트의 역할을 상세히 설명합니다. 시스템을 이해하고 확장하는 데 도움이 되길 바랍니다. 