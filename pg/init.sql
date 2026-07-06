-- Create the stocks database
CREATE DATABASE stocks;

-- Connect to the stocks database
\c stocks;

-- Create the stock table
CREATE TABLE stock (
    id SERIAL PRIMARY KEY,
    datetime TIMESTAMP NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    day INT NOT NULL,
    minute INT NOT NULL,
    hour INT NOT NULL,
    stock_code VARCHAR(255) NOT NULL,
    timezone VARCHAR(255),
    open DECIMAL(10, 2),
    high DECIMAL(10, 2),
    low DECIMAL(10, 2),
    close DECIMAL(10, 2),
    volume BIGINT,
    dividends DECIMAL(10, 2),
    stock_splits DECIMAL(10, 2)
    -- Add more additional columns as needed
);

CREATE UNIQUE INDEX stock_datetime_code_idx ON stock (datetime, stock_code);
CREATE INDEX stock_date_idx ON stock (year, month, day, minute, stock_code);

CREATE TABLE public.company_info (
    stock_code VARCHAR(10) NOT NULL,
    info_date DATE NOT NULL,  -- Changed column name from current_date to info_date
    address1 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    zip VARCHAR(20),
    country VARCHAR(100),
    phone VARCHAR(20),
    website VARCHAR(255),
    industry VARCHAR(100),
    sector VARCHAR(100),
    long_business_summary TEXT,
    full_time_employees INT,
    audit_risk INT,
    board_risk INT,
    compensation_risk INT,
    share_holder_rights_risk INT,
    overall_risk INT,
    ir_website VARCHAR(255),
    previous_close NUMERIC,
    open NUMERIC,
    day_low NUMERIC,
    day_high NUMERIC,
    regular_market_previous_close NUMERIC,
    regular_market_open NUMERIC,
    regular_market_day_low NUMERIC,
    regular_market_day_high NUMERIC,
    ex_dividend_date DATE,
    beta NUMERIC,
    trailing_pe NUMERIC,
    forward_pe NUMERIC,
    volume BIGINT,
    average_volume BIGINT,
    bid NUMERIC,
    ask NUMERIC,
    bid_size INT,
    ask_size INT,
    market_cap BIGINT,
    fifty_two_week_low NUMERIC,
    fifty_two_week_high NUMERIC,
    price_to_sales_trailing_12_months NUMERIC,
    fifty_day_average NUMERIC,
    two_hundred_day_average NUMERIC,
    currency VARCHAR(10),
    enterprise_value BIGINT,
    profit_margins NUMERIC,
    float_shares BIGINT,
    shares_outstanding BIGINT,
    shares_short BIGINT,
    shares_short_prior_month BIGINT,
    shares_short_previous_month_date DATE,
    date_short_interest DATE,
    shares_percent_shares_out NUMERIC,
    held_percent_insiders NUMERIC,
    held_percent_institutions NUMERIC,
    short_ratio NUMERIC,
    short_percent_of_float NUMERIC,
    implied_shares_outstanding BIGINT,
    book_value NUMERIC,
    price_to_book NUMERIC,
    last_fiscal_year_end DATE,
    next_fiscal_year_end DATE,
    most_recent_quarter DATE,
    earnings_quarterly_growth NUMERIC,
    net_income_to_common BIGINT,
    trailing_eps NUMERIC,
    forward_eps NUMERIC,
    peg_ratio NUMERIC,
    last_split_factor VARCHAR(10),
    last_split_date DATE,
    enterprise_to_revenue NUMERIC,
    enterprise_to_ebitda NUMERIC,
    week_change NUMERIC,
    sand_p_week_change NUMERIC,
    exchange VARCHAR(10),
    quote_type VARCHAR(10),
    symbol VARCHAR(10),
    underlying_symbol VARCHAR(10),
    short_name VARCHAR(255),
    long_name VARCHAR(255),
    first_trade_date_epoch_utc BIGINT,
    time_zone_full_name VARCHAR(100),
    time_zone_short_name VARCHAR(10),
    uuid UUID,
    message_board_id VARCHAR(100),
    gmt_offset_milliseconds BIGINT,
    current_price NUMERIC,
    target_high_price NUMERIC,
    target_low_price NUMERIC,
    target_mean_price NUMERIC,
    target_median_price NUMERIC,
    recommendation_mean NUMERIC,
    recommendation_key VARCHAR(10),
    number_of_analyst_opinions INT,
    total_cash BIGINT,
    total_cash_per_share NUMERIC,
    ebitda BIGINT,
    total_debt BIGINT,
    quick_ratio NUMERIC,
    current_ratio NUMERIC,
    total_revenue BIGINT,
    debt_to_equity NUMERIC,
    revenue_per_share NUMERIC,
    return_on_assets NUMERIC,
    return_on_equity NUMERIC,
    free_cashflow BIGINT,
    operating_cashflow BIGINT,
    earnings_growth NUMERIC,
    revenue_growth NUMERIC,
    gross_margins NUMERIC,
    ebitda_margins NUMERIC,
    operating_margins NUMERIC,
    financial_currency VARCHAR(10),
    trailing_peg_ratio NUMERIC,
    PRIMARY KEY (stock_code, info_date)
);

DROP TABLE IF EXISTS stock_news;

-- Create the stock_news table
CREATE TABLE stock_news (
	stock_code varchar(50) NOT NULL,
	"date" date NOT NULL,
	url text NOT NULL,
	title text NULL,
	detail text NULL,
	sentiment_score float8 NOT NULL DEFAULT 0,
	"sentiment_finbert-tone" float8 NOT NULL DEFAULT 0,
	CONSTRAINT stock_news_pkey PRIMARY KEY (date, stock_code, url)
);

-- Add comments for clarity (optional)
COMMENT ON COLUMN stock_news.stock_code IS 'The stock code associated with the news article';
COMMENT ON COLUMN stock_news.date IS 'The date of the news article';
COMMENT ON COLUMN stock_news.url IS 'The URL of the news article';
COMMENT ON COLUMN stock_news.title IS 'The title of the news article';
COMMENT ON COLUMN stock_news.detail IS 'The body text of the news article';
COMMENT ON COLUMN stock_news.score IS 'A score related to the news article, stored as a float';
