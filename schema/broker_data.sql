CREATE TABLE broker_data (
    when_added   TIMESTAMP NOT NULL,
    record_time  TIMESTAMP NOT NULL,
    stocks       VARCHAR(50) NOT NULL,
    exchange     VARCHAR(50) NOT NULL,
    open         DECIMAL(12,4),
    close        DECIMAL(12,4),
    low          DECIMAL(12,4),
    high         DECIMAL(12,4),
    volume       BIGINT,
    broker_name  VARCHAR(100),
    granularity  VARCHAR(20)
);

-- Index for when_added (sorted)
CREATE INDEX idx_broker_data_when_added ON broker_data (when_added);

-- Index for stocks
CREATE INDEX idx_broker_data_stocks ON broker_data (stocks);

-- Index for exchange
CREATE INDEX idx_broker_data_exchange ON broker_data (exchange);

-- Composite Index for stocks and record_time
CREATE INDEX idx_broker_data_stocks_record_time ON broker_data (stocks, record_time);

-- Composite Index for exchange and record_time
CREATE INDEX idx_broker_data_exchange_record_time ON broker_data (exchange, record_time);

-- Composite Index for stocks, exchange, and record_time
CREATE INDEX idx_broker_data_stocks_exchange_record_time ON broker_data (stocks, exchange,
    record_time);

-- Unique constraint to prevent duplicate entries
ALTER TABLE broker_data
ADD CONSTRAINT uq_broker_data_unique_entry UNIQUE (record_time, stocks, exchange, granularity);
