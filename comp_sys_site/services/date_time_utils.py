from datetime import datetime


def get_current_year():
    """Gets the current year as an integer."""
    current_date = datetime.now()
    current_date = current_date.strftime("%Y")
    return int(current_date)
