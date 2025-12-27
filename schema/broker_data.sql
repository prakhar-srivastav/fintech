CREATE TABLE broker_data (
    when_added   TIMESTAMP NOT NULL,
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
