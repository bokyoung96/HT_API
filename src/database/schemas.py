# NOTE: 1m futures data
def create_futures_table_sql(symbol: str) -> str:
    # Use first 3 chars for table name (e.g., 101W09 -> 101)
    table_name_suffix = symbol[:3].lower()
    table_name = f"futures_{table_name_suffix}"
    return f"""
CREATE TABLE IF NOT EXISTS {table_name} (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    open NUMERIC(10,2) NOT NULL,
    high NUMERIC(10,2) NOT NULL,
    low NUMERIC(10,2) NOT NULL,
    close NUMERIC(10,2) NOT NULL,
    volume BIGINT NOT NULL,
    UNIQUE(timestamp, symbol)
);

CREATE INDEX IF NOT EXISTS idx_{table_name}_timestamp ON {table_name}(timestamp);
CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol ON {table_name}(symbol);
"""

# NOTE: 1m stocks data
STOCKS_1M_TABLE = """
CREATE TABLE IF NOT EXISTS stocks_1m (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe INTEGER NOT NULL,
    open NUMERIC(10,2) NOT NULL,
    high NUMERIC(10,2) NOT NULL,
    low NUMERIC(10,2) NOT NULL,
    close NUMERIC(10,2) NOT NULL,
    volume BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(timestamp, symbol, timeframe)
);

CREATE INDEX IF NOT EXISTS idx_stocks_1m_timestamp ON stocks_1m(timestamp);
CREATE INDEX IF NOT EXISTS idx_stocks_1m_symbol ON stocks_1m(symbol);
"""

# NOTE: option chain raw data
OPTION_CHAIN_RAW_TABLE = """
CREATE TABLE IF NOT EXISTS option_chain_raw (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    underlying_symbol VARCHAR(20) NOT NULL,
    underlying_price NUMERIC(10,2) NOT NULL,
    option_symbol VARCHAR(50) NOT NULL,
    option_type CHAR(1) NOT NULL, -- 'C' or 'P'
    strike_price NUMERIC(10,2) NOT NULL,
    atm_class VARCHAR(10) NOT NULL, -- 'ITM', 'ATM', 'OTM'
    price NUMERIC(10,4) NOT NULL,
    iv NUMERIC(8,4) NOT NULL,
    delta NUMERIC(8,4) NOT NULL,
    gamma NUMERIC(8,4) NOT NULL,
    vega NUMERIC(8,4) NOT NULL,
    theta NUMERIC(8,4) NOT NULL,
    rho NUMERIC(8,4) NOT NULL,
    volume INTEGER NOT NULL,
    open_interest INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_option_chain_timestamp ON option_chain_raw(timestamp);
CREATE INDEX IF NOT EXISTS idx_option_chain_underlying ON option_chain_raw(underlying_symbol);
CREATE INDEX IF NOT EXISTS idx_option_chain_strike ON option_chain_raw(strike_price);
CREATE INDEX IF NOT EXISTS idx_option_chain_atm_class ON option_chain_raw(atm_class);
"""

# NOTE:1m option matrices
def create_option_matrices_table_sql(underlying_symbol: str) -> str:
    table_name = f"option_matrices_{underlying_symbol.lower()}"
    return f"""
CREATE TABLE IF NOT EXISTS {table_name} (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    underlying_symbol VARCHAR(50) NOT NULL,
    metric_type VARCHAR(20) NOT NULL,
    
    -- Call Options
    c_itm10 NUMERIC(8,4), c_itm9 NUMERIC(8,4), c_itm8 NUMERIC(8,4), c_itm7 NUMERIC(8,4), c_itm6 NUMERIC(8,4),
    c_itm5 NUMERIC(8,4), c_itm4 NUMERIC(8,4), c_itm3 NUMERIC(8,4), c_itm2 NUMERIC(8,4), c_itm1 NUMERIC(8,4),
    c_atm NUMERIC(8,4),
    c_otm1 NUMERIC(8,4), c_otm2 NUMERIC(8,4), c_otm3 NUMERIC(8,4), c_otm4 NUMERIC(8,4), c_otm5 NUMERIC(8,4),
    c_otm6 NUMERIC(8,4), c_otm7 NUMERIC(8,4), c_otm8 NUMERIC(8,4), c_otm9 NUMERIC(8,4), c_otm10 NUMERIC(8,4),
    
    -- Put Options
    p_itm10 NUMERIC(8,4), p_itm9 NUMERIC(8,4), p_itm8 NUMERIC(8,4), p_itm7 NUMERIC(8,4), p_itm6 NUMERIC(8,4),
    p_itm5 NUMERIC(8,4), p_itm4 NUMERIC(8,4), p_itm3 NUMERIC(8,4), p_itm2 NUMERIC(8,4), p_itm1 NUMERIC(8,4),
    p_atm NUMERIC(8,4),
    p_otm1 NUMERIC(8,4), p_otm2 NUMERIC(8,4), p_otm3 NUMERIC(8,4), p_otm4 NUMERIC(8,4), p_otm5 NUMERIC(8,4),
    p_otm6 NUMERIC(8,4), p_otm7 NUMERIC(8,4), p_otm8 NUMERIC(8,4), p_otm9 NUMERIC(8,4), p_otm10 NUMERIC(8,4),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(timestamp, underlying_symbol, metric_type)
);

CREATE INDEX IF NOT EXISTS idx_{table_name}_timestamp ON {table_name}(timestamp);
CREATE INDEX IF NOT EXISTS idx_{table_name}_metric ON {table_name}(metric_type);
"""

# NOTE: system status and log data
SYSTEM_STATUS_TABLE = """
CREATE TABLE IF NOT EXISTS system_status (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    component VARCHAR(50) NOT NULL, -- 'futures_fetcher', 'option_chain_fetcher', etc
    status VARCHAR(20) NOT NULL,     -- 'running', 'stopped', 'error'
    message TEXT,
    data_count INTEGER DEFAULT 0,
    last_data_time TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_system_status_timestamp ON system_status(timestamp);
CREATE INDEX IF NOT EXISTS idx_system_status_component ON system_status(component);
"""

# NOTE: dolpha1 signal table
DOLPHA1_SIGNAL_TABLE = """
CREATE TABLE IF NOT EXISTS dolpha1_signal (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume BIGINT,
    vwap DOUBLE PRECISION,
    atr DOUBLE PRECISION,
    sigma_open DOUBLE PRECISION,
    ub DOUBLE PRECISION,
    lb DOUBLE PRECISION,
    entry_signal INTEGER,
    entry_reason TEXT,
    exit_signal INTEGER,
    exit_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (timestamp, symbol)
);

CREATE INDEX IF NOT EXISTS idx_dolpha1_signal_timestamp ON dolpha1_signal(timestamp);
CREATE INDEX IF NOT EXISTS idx_dolpha1_signal_symbol ON dolpha1_signal(symbol);
CREATE INDEX IF NOT EXISTS idx_dolpha1_signal_entry_signal ON dolpha1_signal(entry_signal);
CREATE INDEX IF NOT EXISTS idx_dolpha1_signal_exit_signal ON dolpha1_signal(exit_signal);
"""

# NOTE: static tables
ALL_STATIC_TABLES = [
    STOCKS_1M_TABLE,
    OPTION_CHAIN_RAW_TABLE,
    SYSTEM_STATUS_TABLE,
    DOLPHA1_SIGNAL_TABLE
]
