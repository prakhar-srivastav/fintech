1. the strategy run page to become strategy scheudle page.
2. we can schedule a strategy by uploading the job into database
3. we can view all the scheduled strategies in the strategy schedule page
4. upon clicking on a scheduled strategy we can view the details of the strategy
5. a scheduler should run to pick the scheduled strategies and run them, one at time
6. since each strategy show a card indiciating a stock, we should be able to run a 'execute a strategy'
7. enter 'executer' page and pod that will execute a strategy end to end. Need to research on it. Think like play, execute, schedule option.
8. execute will show all the status with the final selected config. ofcourse in real and stimulation mode
9. if real, ask for money and distribute it with some heuristics
10. every update to be reflected in database
11. instead of top 50, we should be able to run on all bse and nse stocsk
12. search bar to be added that will fetch the entry from the database
13. for real mode, we need to make sure we intergrated that service


GTT Types:
Single Trigger - One trigger price, one order

Example: "Buy RELIANCE when price drops to ₹2400"
OCO (One Cancels Other) - Two triggers (stop-loss + target)

    Example: "Sell RELIANCE if price goes above ₹2600 OR below ₹2300"

Integrate GTT / OCO