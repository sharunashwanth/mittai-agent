from datetime import datetime, timezone

from langchain_core.tools import tool


@tool
def get_current_datetime() -> dict:
    """
    Get the current date and time in UTC timezone.
    Returns:
        Dictionary with current date, time, and datetime in ISO format
    """
    now = datetime.now(timezone.utc)
    return {
        "current_date": now.date().isoformat(),
        "current_time": now.time().strftime("%H:%M:%S"),
        "current_datetime": now.isoformat(),
        "date_formatted": now.strftime("%Y-%m-%d"),
        "time_formatted": now.strftime("%H:%M:%S"),
        "datetime_formatted": now.strftime("%Y-%m-%d %H:%M:%S"),
    }
