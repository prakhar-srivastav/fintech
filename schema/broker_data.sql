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

-- ============================================================================
-- Strategy Execution Tables
-- ============================================================================

-- Table to store strategy execution requests
CREATE TABLE strategy_executions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_id INT NOT NULL,
    status VARCHAR(20) DEFAULT 'queued',
    stimulate_mode BOOLEAN DEFAULT TRUE,
    total_money DECIMAL(15,2) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    error_message TEXT,
    
    -- Foreign key to strategy_runs
    CONSTRAINT fk_strategy_executions_run FOREIGN KEY (strategy_id) 
        REFERENCES strategy_runs(id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_strategy_executions_strategy_id (strategy_id),
    INDEX idx_strategy_executions_status (status),
    INDEX idx_strategy_executions_created_at (created_at)
);

-- Table to store which strategy results are included in an execution
CREATE TABLE strategy_execution_details (
    id INT AUTO_INCREMENT PRIMARY KEY,
    execution_id INT NOT NULL,
    strategy_result_id INT NOT NULL,
    weight_percent DECIMAL(5,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'queued',
    
    -- Foreign keys
    CONSTRAINT fk_execution_details_execution FOREIGN KEY (execution_id) 
        REFERENCES strategy_executions(id) ON DELETE CASCADE,
    CONSTRAINT fk_execution_details_result FOREIGN KEY (strategy_result_id) 
        REFERENCES strategy_results(id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_execution_details_execution_id (execution_id),
    INDEX idx_execution_details_result_id (strategy_result_id),
    
    -- Unique constraint to prevent duplicate entries
    UNIQUE KEY uq_execution_details_unique (execution_id, strategy_result_id)
);

-- Table to store strategy execution tasks (individual trade tasks)
CREATE TABLE strategy_execution_tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    execution_detail_id INT NOT NULL,
    timestamp_of_execution INT(50),
    day_of_execution VARCHAR(50),
    current_money DECIMAL(15,2),
    current_shares INT DEFAULT 0,
    price_during_order DECIMAL(12,4) NULL,
    order_type VARCHAR(10) DEFAULT 'buy',
    stimulate_mode BOOLEAN DEFAULT TRUE,
    x INT(50),
    y INT(50),
    stock VARCHAR(50),
    exchange VARCHAR(50),
    days_remaining INT DEFAULT 0,
    previous_task_id INT DEFAULT -1,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMP NULL,
    error_message TEXT,
    
    -- Foreign key to strategy_execution_details
    CONSTRAINT fk_execution_tasks_detail FOREIGN KEY (execution_detail_id) 
        REFERENCES strategy_execution_details(id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_execution_tasks_detail_id (execution_detail_id),
    INDEX idx_execution_tasks_status (status),
    INDEX idx_execution_tasks_created_at (created_at),
    INDEX idx_execution_tasks_stock (stock),
    INDEX idx_execution_tasks_order_type (order_type),
    INDEX idx_execution_tasks_timestamp (timestamp_of_execution)
);

-- Table to store task execution output/results
CREATE TABLE strategy_execution_tasks_output (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT NOT NULL,
    order_id VARCHAR(100),
    shares_bought INT DEFAULT 0,
    price_per_share DECIMAL(12,4),
    total_amount DECIMAL(15,2),
    money_provided DECIMAL(15,2),
    money_remaining DECIMAL(15,2),
    order_timestamp TIMESTAMP NULL,
    exchange_timestamp TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key to strategy_execution_tasks
    CONSTRAINT fk_tasks_output_task FOREIGN KEY (task_id) 
        REFERENCES strategy_execution_tasks(id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_tasks_output_task_id (task_id),
    INDEX idx_tasks_output_order_id (order_id),
    
    -- One output per task
    UNIQUE KEY uq_tasks_output_task (task_id)
);
