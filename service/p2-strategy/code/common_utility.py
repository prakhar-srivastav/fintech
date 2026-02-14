from datetime import datetime, timedelta

def is_trading_day_nse(date):
    """Check if a given date is a trading day for NSE"""
    # NSE 2026 holidays
    nse_holidays = [
        '2026-01-26',  # Republic Day
        '2026-03-14',  # Holi
        '2026-03-30',  # Ram Navami
        '2026-04-02',  # Mahavir Jayanti
        '2026-04-03',  # Good Friday
        '2026-04-14',  # Ambedkar Jayanti
        '2026-05-01',  # Maharashtra Day
        '2026-08-15',  # Independence Day
        '2026-08-31',  # Ganesh Chaturthi
        '2026-10-02',  # Gandhi Jayanti
        '2026-10-20',  # Dussehra
        '2026-10-21',  # Diwali Balipratipada
        '2026-11-04',  # Diwali Laxmi Pujan
        '2026-11-16',  # Gurunanak Jayanti
        '2026-12-25',  # Christmas
    ]

    date_str = date.strftime('%Y-%m-%d')
    return date_str not in nse_holidays


def is_trading_day_bse(date):
    """Check if a given date is a trading day for BSE"""
    # BSE 2026 holidays
    bse_holidays = [
        '2026-01-26',  # Republic Day
        '2026-03-14',  # Holi
        '2026-03-30',  # Ram Navami
        '2026-04-02',  # Mahavir Jayanti
        '2026-04-03',  # Good Friday
        '2026-04-14',  # Ambedkar Jayanti
        '2026-05-01',  # Maharashtra Day
        '2026-08-15',  # Independence Day
        '2026-08-31',  # Ganesh Chaturthi
        '2026-10-02',  # Gandhi Jayanti
        '2026-10-20',  # Dussehra
        '2026-10-21',  # Diwali Balipratipada
        '2026-11-04',  # Diwali Laxmi Pujan
        '2026-11-16',  # Gurunanak Jayanti
        '2026-12-25',  # Christmas
    ]

    date_str = date.strftime('%Y-%m-%d')
    return date_str not in bse_holidays

def get_next_business_day(current_date, exchange):
    """
    Get the next business day for the given exchange.
    """
    itr = 100
    while True:
        current_date += timedelta(days=1)
        if current_date.weekday() >= 5:  # Skip weekends
            continue
        if exchange == 'NSE' and not is_trading_day_nse(current_date):
            continue
        if exchange == 'BSE' and not is_trading_day_bse(current_date):
            continue
        itr -= 1
        if itr <= 0:
            raise Exception("Too many iterations while finding next business day")
        return current_date