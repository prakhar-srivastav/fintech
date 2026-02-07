'broker_data'
'default_strategy_config' - default cofniguration displayed by the UI
'strategy_execution_details'
'strategy_execution_tasks'
'strategy_execution_tasks_output'
'strategy_executions' - Now, I take a special run and trigger it, it will be put here
    'strategy_results' - a particular run's result of strategy_runs
    'strategy_runs' - when we click on config in the UI, the data is here


strategy_runs -> 
1. {"end_date": "2026-01-25", "sync_data": true, "bse_stocks": ["RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR", "ICICIBANK", "SBIN", "KOTAKBANK", "LT", "AXISBANK"], "nse_stocks": ["RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR", "ICICIBANK", "SBIN", "KOTAKBANK", "LT", "AXISBANK"], "start_date": "2025-10-27", "granularity": "3minute", "vertical_gaps": [0.5, 1, 2], "continuous_days": [5], "horizontal_gaps": [2]}
2. I can select a configuration to run from the UI to find the best match and run it.

strategy_result ->
1. a particular run's result of strategy_runs
2. It will have the result of all the tasks executed in that run.

strategy_executions and strategy_execution_details ->
1. Now, I will take a run and trigger some of the stocks for it
2. strategy_executions will have global details like strategy_run_id, stimulate_mode and money_allocated
3. strategy_execution_details will have stock specific details like weighed_score and strategy_result_id reference

strategy_execution_tasks and strategy_execution_tasks_output ->
1. daywise task for a particular execution_detail_id will be in strategy_execution_tasks
2. strategy_execution_tasks_output will have the output of those tasks.

status flow ->

strategy_runs.status -> queued -> running -> completed/failed
strategy_executions.status -> queued -> running -> completed/failed
strategy_execution_details.status -> queued -> running -> completed/failed
strategy_execution_tasks.status -> queued -> running -> completed/failed