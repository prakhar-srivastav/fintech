RoadMap :

1. Focus on initial development focusing on algorithm / poc rather than platofromization / scalability.
    - stocks api for crypto, mfs, stocks etc
    - accuracy of data
    - correctness of the strategies
    - stimulation implementation - try of different configuration to see which have highest revenue 
    - real money interaction
    - past data validations
    - whether our strategy is actually working on real live data or not

1.5. Enhance if there is a need

2. Create a scrappy UI just to have some visibility of how the strategy is working for a specific run. This needs a db as well and some trade orchestrator

3. Platformization : 
    stocks 
        - interface for getting all the stocks information from different accounts like 
            binance, zerodha etc.
        - responsible for data gathering
        - possibly stores the past transcational details
        - accuracy of the data.
        - can also record past transcation data for a specific stocks on its participation in
            different startegy and gain/loss made over stimulated or real money
    strategizer-x
        - implementation of strategy of type x
        - given a configuration, it will run the strategy instance
        - talks to transcation service for completing order if required
        - can work on past data
        - can work on real time woth real money
        - can work on real time with no money (stimulation)
        - it also commits the transcation and current run status to the database
    database
        - stores stocks, run data
        - stores transcation data  
    ui
        - stimulation UI -> runs the scan -> gives the stimulation top3 config with probability
        - for a config -> show the stocks wise performance -
            stock1 - - - -
            stock2 - - - -
            stock3 - - - -
        - Scheduler UI -> takes the money info as well.
    Grouper
        - finds the best stock grouping based on certai criteria mentioned in stocks_groups.md
    transcation
        - actual account level transcation, may or may not be a part of stocks resources
    