# Finance Making Algorithm:
———————————————
    1. There should be market stimulation mode and real money mode.
        1. Maket-stimulation :
            1. Your strategy x will be applied without real money.
            2. Your strategy x will be applied over the past data.
        2. Real money mode:
            1. Your strategy x will be applied with real money.
    2. Stock selection
        1. Stocks -> classic, crypto, mutuals
        2. Block-allow stock units.
        3. Stock groups - select almost x stock per group
        4. Overlap_threshold - how many candidates points are allowed from the same stocks.
    3. Strategy
        1. For a stock x, select two point/range where the difference is high over last y days continuously for z such segments.
        2. Point/range size is l. Highest of lower range of l should be lesser than lowest of higher range. 
        3. Stop loss -> sl%
        4. Early Exit -> ee%
        5. Implement this strategy for exec number of days.
    4. Stimulation - apply market-stimulation of past data and select the best strategy. Apply for one to two time without real money. Then apply with real money.

