CREATE TABLE broker_data (
    when_added   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    record_time  TIMESTAMP NOT NULL,
    stock       VARCHAR(50) NOT NULL,
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

-- Index for stock
CREATE INDEX idx_broker_data_stock ON broker_data (stock);

-- Index for exchange
CREATE INDEX idx_broker_data_exchange ON broker_data (exchange);

-- Index for record_time
CREATE INDEX idx_broker_data_record_time ON broker_data (record_time);

-- Composite Index for stock and record_time
CREATE INDEX idx_broker_data_stock_record_time ON broker_data (stock, record_time);

-- Composite Index for exchange and record_time
CREATE INDEX idx_broker_data_exchange_record_time ON broker_data (exchange, record_time);

-- Composite Index for stock, exchange, and record_time
CREATE INDEX idx_broker_data_stock_exchange_record_time ON broker_data (stock, exchange,
    record_time);

-- Unique constraint to prevent duplicate entries
ALTER TABLE broker_data
ADD CONSTRAINT uq_broker_data_unique_entry UNIQUE (record_time, stock, exchange, granularity);
