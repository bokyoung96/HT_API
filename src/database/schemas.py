# NOTE: 1m futures data
FUTURES_1M_TABLE = """
CREATE TABLE IF NOT EXISTS futures_1m (
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

CREATE INDEX IF NOT EXISTS idx_futures_1m_timestamp ON futures_1m(timestamp);
CREATE INDEX IF NOT EXISTS idx_futures_1m_symbol ON futures_1m(symbol);
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

# NOTE: option matrices data
OPTION_MATRICES_TABLE = """
CREATE TABLE IF NOT EXISTS option_matrices (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    underlying_symbol VARCHAR(20) NOT NULL,
    metric_type VARCHAR(10) NOT NULL, -- 'iv', 'delta', 'gamma', 'vega', 'theta', 'rho'
    
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

CREATE INDEX IF NOT EXISTS idx_option_matrices_timestamp ON option_matrices(timestamp);
CREATE INDEX IF NOT EXISTS idx_option_matrices_metric ON option_matrices(metric_type);
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

# NOTE: all tables
ALL_TABLES = [
    FUTURES_1M_TABLE,
    STOCKS_1M_TABLE,
    OPTION_CHAIN_RAW_TABLE,
    OPTION_MATRICES_TABLE,
    SYSTEM_STATUS_TABLE
]
