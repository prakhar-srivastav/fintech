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
