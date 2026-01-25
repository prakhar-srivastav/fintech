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

-- ============================================================================
-- Strategy Tables for P2 Strategy Dashboard
-- ============================================================================

-- Table to store strategy run metadata
CREATE TABLE strategy_runs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    when_added TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL,
    config JSON,
    status VARCHAR(20) DEFAULT 'queued',
    description VARCHAR(255),
    INDEX idx_strategy_runs_when_added (when_added),
    INDEX idx_strategy_runs_status (status)
);

-- Table to store strategy results
CREATE TABLE strategy_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_id INT NOT NULL,
    stock VARCHAR(50) NOT NULL,
    exchange VARCHAR(50) NOT NULL,
    x VARCHAR(50),
    y VARCHAR(50),
    exceed_prob DECIMAL(10,6),
    profit_days INT,
    average DECIMAL(12,4),
    total_count INT,
    highest DECIMAL(12,4),
    p5 DECIMAL(12,4),
    p10 DECIMAL(12,4),
    p20 DECIMAL(12,4),
    p40 DECIMAL(12,4),
    p50 DECIMAL(12,4),
    vertical_gap DECIMAL(10,4),
    horizontal_gap DECIMAL(10,4),
    continuous_days INT,
    when_added TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key to strategy_runs
    CONSTRAINT fk_strategy_results_run FOREIGN KEY (strategy_id) 
        REFERENCES strategy_runs(id) ON DELETE CASCADE,
    
    -- Indexes for common queries
    INDEX idx_strategy_results_strategy_id (strategy_id),
    INDEX idx_strategy_results_stock (stock),
    INDEX idx_strategy_results_exchange (exchange),
    INDEX idx_strategy_results_exceed_prob (exceed_prob),
    INDEX idx_strategy_results_stock_exchange (stock, exchange),
    
    -- Unique constraint to prevent duplicate entries for same config
    UNIQUE KEY uq_strategy_results_unique 
        (strategy_id, stock, exchange, x, y, vertical_gap, horizontal_gap, continuous_days)
);

-- Table to store default strategy configuration
CREATE TABLE default_strategy_config (
    parameter VARCHAR(50) PRIMARY KEY,
    value TEXT NOT NULL,
    description VARCHAR(255)
);

-- Insert default configuration values
INSERT INTO default_strategy_config (parameter, value, description) VALUES
    ('vertical_gaps', '0.5,1,2', 'Vertical gap percentages'),
    ('horizontal_gaps', '2', 'Horizontal gap values'),
    ('continuous_days', '3,5,7,10', 'Number of continuous days'),
    ('granularity', '3minute', 'Data granularity');
