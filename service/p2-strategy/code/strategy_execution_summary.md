- update strategy_execution_summary table:
            execution of execution_id x
            [
            stock name : 
            exchange : 
            money planned : 
            weight percent :
            x - >  y
            continuous days :
            horizontal-gap : 
            vertical-gap : 
            exceed_prob :
            average :

            current_day : x/total_days
            profit_earned : 
            expected_profit_based_on_average :
            detailed_view: [
            day1 - buy : order_id, shares_bought, price_per_share, total_amount, money_provided, money_remaining, order_timestamp, exchange_timestamp, profit_earned, expected_profit_based_on_average
            day1 - sell : order_id, shares_sold, price_per_share, total_amount, money_provided, money_remaining, order_timestamp, exchange_timestamp, profit_earned, expected_profit_based_on_average
            day2 - buy : order_id, shares_bought, price_per_share, total_amount, money_provided, money_remaining, order_timestamp, exchange_timestamp, profit_earned, expected_profit_based_on_average
            day2 - sell : order_id, shares_sold, price_per_share, total_amount, money_provided, money_remaining, order_timestamp, exchange_timestamp, profit_earned, expected_profit_based_on_average
            ]


            ]
            
            [
            day1 - buy : order_id, shares_bought, price_per_share, total_amount, money_provided, money_remaining, order_timestamp, exchange_timestamp, profit_earned, expected_profit_based_on_average
            day1 - sell : order_id, shares_sold, price_per_share, total_amount, money_provided, money_remaining, order_timestamp, exchange_timestamp, profit_earned, expected_profit_based_on_average
            day2 - buy : order_id, shares_bought, price_per_share, total_amount, money_provided, money_remaining, order_timestamp, exchange_timestamp, profit_earned, expected_profit_based_on_average
            day2 - sell : order_id, shares_sold, price_per_share, total_amount, money_provided, money_remaining, order_timestamp, exchange_timestamp, profit_earned, expected_profit_based_on_average
            ]
        if failure:
         - update the strategy_execution_tasks table with status = failed, error_message = ...
    