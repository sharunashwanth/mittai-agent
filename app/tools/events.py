from datetime import date, time

from database import get_session
from langchain_core.tools import tool
from models import Event


@tool
def create_event(
    title: str, event_date: str, start_time: str, end_time: str, description: str = ""
) -> dict:
    """
    Create a new event in the database.
    Args:
        title: Event title
        event_date: Date in YYYY-MM-DD format (e.g., "2024-01-15")
        start_time: Start time in HH:MM format in 24-hour format (e.g., "14:30")
        end_time: End time in HH:MM format in 24-hour format (e.g., "16:00")
        description: Optional event description
    Returns:
        Dictionary with event details or error message
    """
    try:
        event_date_obj = date.fromisoformat(event_date)
        start_time_obj = time.fromisoformat(start_time)
        end_time_obj = time.fromisoformat(end_time)

        with get_session() as session:
            event = Event(
                title=title,
                description=description,
                event_date=event_date_obj,
                event_start_time=start_time_obj,
                event_end_time=end_time_obj,
            )
            session.add(event)
            session.commit()
            session.refresh(event)

            return {
                "status": "success",
                "event_id": event.id,
                "title": event.title,
                "description": event.description,
                "date": str(event.event_date),
                "start_time": str(event.event_start_time),
                "end_time": str(event.event_end_time),
            }
    except ValueError as e:
        return {"status": "error", "message": f"Invalid date/time format: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@tool
def check_event_exists(event_date: str) -> dict:
    """
    Check if any events exist on a given date.
    Args:
        event_date: Date in YYYY-MM-DD format (e.g., "2024-01-15")
    Returns:
        Dictionary with existence status and event details if found
    """
    try:
        event_date_obj = date.fromisoformat(event_date)
        with get_session() as session:
            events = (
                session.query(Event).filter(Event.event_date == event_date_obj).all()
            )

            if events:
                return {
                    "exists": True,
                    "count": len(events),
                    "events": [
                        {
                            "id": e.id,
                            "title": e.title,
                            "start_time": str(e.event_start_time),
                            "end_time": str(e.event_end_time),
                            "description": e.description,
                        }
                        for e in events
                    ],
                }
            return {"exists": False, "count": 0}
    except ValueError as e:
        return {"status": "error", "message": f"Invalid date format: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@tool
def get_event_by_id(event_id: int) -> dict:
    """
    Get a specific event by its ID.
    Args:
        event_id: The ID of the event
    Returns:
        Dictionary with event details or error message
    """
    try:
        with get_session() as session:
            event = session.query(Event).filter(Event.id == event_id).first()

            if event:
                return {
                    "status": "success",
                    "event": {
                        "id": event.id,
                        "title": event.title,
                        "description": event.description,
                        "date": str(event.event_date),
                        "start_time": str(event.event_start_time),
                        "end_time": str(event.event_end_time),
                        "created_at": str(event.created_at),
                    },
                }
            return {
                "status": "error",
                "message": f"Event with ID {event_id} not found",
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@tool
def query_events(
    start_date: str = None, end_date: str = None, keyword: str = None
) -> dict:
    """
    Query events from the database. Can filter by date range or keyword.
    Args:
        start_date: Optional start date in YYYY-MM-DD format for date range filtering
        end_date: Optional end date in YYYY-MM-DD format for date range filtering
        keyword: Optional keyword to search in event titles/descriptions
    Returns:
        Dictionary with list of events
    """
    try:
        with get_session() as session:
            query = session.query(Event)

            if start_date:
                start_date_obj = date.fromisoformat(start_date)
                query = query.filter(Event.event_date >= start_date_obj)

            if end_date:
                end_date_obj = date.fromisoformat(end_date)
                query = query.filter(Event.event_date <= end_date_obj)

            if keyword:
                query = query.filter(
                    (Event.title.contains(keyword))
                    | (Event.description.contains(keyword))
                )

            events = query.order_by(Event.event_date, Event.event_start_time).all()

            return {
                "status": "success",
                "count": len(events),
                "events": [
                    {
                        "id": e.id,
                        "title": e.title,
                        "description": e.description,
                        "date": str(e.event_date),
                        "start_time": str(e.event_start_time),
                        "end_time": str(e.event_end_time),
                    }
                    for e in events
                ],
            }
    except ValueError as e:
        return {"status": "error", "message": f"Invalid date format: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@tool
def delete_event(event_id: int) -> dict:
    """
    Delete an event from the database.
    Args:
        event_id: The ID of the event to delete
    Returns:
        Dictionary with deletion status
    """
    try:
        with get_session() as session:
            event = session.query(Event).filter(Event.id == event_id).first()

            if event:
                session.delete(event)
                session.commit()
                return {
                    "status": "success",
                    "message": f"Event '{event.title}' (ID: {event_id}) deleted successfully",
                }
            return {
                "status": "error",
                "message": f"Event with ID {event_id} not found",
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}
