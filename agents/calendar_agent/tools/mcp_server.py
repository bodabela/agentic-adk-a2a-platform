"""MCP server for calendar_agent - calendar management tools with mock data."""

from datetime import datetime, timedelta
import json

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("CalendarServer")


def _today() -> datetime:
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


@mcp.tool()
def get_today() -> dict:
    """Get today's date and current time information.

    Returns:
        Dictionary with today's date, current time, and useful date references
    """
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "status": "success",
        "today": today.strftime("%Y-%m-%d"),
        "now": now.isoformat(),
        "weekday": now.strftime("%A"),
        "month_start": today.replace(day=1).strftime("%Y-%m-%d"),
        "month_end": (today.replace(day=28) + timedelta(days=4)).replace(day=1).strftime("%Y-%m-%d") if today.month < 12 else f"{today.year}-12-31",
        "tomorrow": (today + timedelta(days=1)).strftime("%Y-%m-%d"),
        "next_week_start": (today + timedelta(days=(7 - today.weekday()))).strftime("%Y-%m-%d"),
    }


def _mock_events(start_date: str, end_date: str) -> list[dict]:
    """Generate realistic mock calendar events relative to the given dates."""
    try:
        start = datetime.fromisoformat(start_date)
    except ValueError:
        start = _today()

    events = [
        {
            "event_id": "evt-001",
            "title": "Sprint Planning",
            "start_time": (start.replace(hour=9, minute=0)).isoformat(),
            "end_time": (start.replace(hour=10, minute=0)).isoformat(),
            "attendees": ["Kovács Péter", "Nagy Anna", "Szabó Gábor"],
            "location": "Meeting Room A / Teams",
            "description": "Sprint 24 planning - feature prioritization",
            "status": "confirmed",
        },
        {
            "event_id": "evt-002",
            "title": "1:1 with Nagy Anna",
            "start_time": (start.replace(hour=11, minute=0)).isoformat(),
            "end_time": (start.replace(hour=11, minute=30)).isoformat(),
            "attendees": ["Nagy Anna"],
            "location": "Online - Teams",
            "description": "Weekly sync",
            "status": "confirmed",
        },
        {
            "event_id": "evt-003",
            "title": "Client Review - Acme Corp",
            "start_time": (start.replace(hour=14, minute=0)).isoformat(),
            "end_time": (start.replace(hour=15, minute=30)).isoformat(),
            "attendees": ["Tóth László", "Varga Eszter", "John Smith (Acme)"],
            "location": "Conference Room B",
            "description": "Q1 deliverables review with Acme Corp stakeholders",
            "status": "confirmed",
        },
        {
            "event_id": "evt-004",
            "title": "Team Retrospective",
            "start_time": (start.replace(hour=16, minute=0)).isoformat(),
            "end_time": (start.replace(hour=17, minute=0)).isoformat(),
            "attendees": ["Kovács Péter", "Nagy Anna", "Szabó Gábor", "Kiss Márta", "Horváth Dávid"],
            "location": "Meeting Room A",
            "description": "Sprint 23 retrospective",
            "status": "tentative",
        },
    ]
    return events


@mcp.tool()
def list_events(start_date: str, end_date: str = "") -> dict:
    """List calendar events for a date range.

    Args:
        start_date: Start date in ISO format (e.g. 2026-03-13)
        end_date: End date in ISO format. Defaults to same as start_date.

    Returns:
        Dictionary with list of events
    """
    if not end_date:
        end_date = start_date
    events = _mock_events(start_date, end_date)
    return {
        "status": "success",
        "events": events,
        "event_count": len(events),
        "date_range": {"start": start_date, "end": end_date},
    }


@mcp.tool()
def get_event(event_id: str) -> dict:
    """Get detailed information about a specific calendar event.

    Args:
        event_id: The event identifier (e.g. evt-001)

    Returns:
        Dictionary with event details
    """
    today = _today()
    mock_events = {
        "evt-001": {
            "event_id": "evt-001",
            "title": "Sprint Planning",
            "start_time": today.replace(hour=9).isoformat(),
            "end_time": today.replace(hour=10).isoformat(),
            "attendees": [
                {"name": "Kovács Péter", "email": "kovacs.peter@company.hu", "response": "accepted"},
                {"name": "Nagy Anna", "email": "nagy.anna@company.hu", "response": "accepted"},
                {"name": "Szabó Gábor", "email": "szabo.gabor@company.hu", "response": "tentative"},
            ],
            "location": "Meeting Room A / Teams",
            "description": "Sprint 24 planning - feature prioritization",
            "organizer": "Kovács Péter",
            "created": (today - timedelta(days=5)).isoformat(),
            "recurring": True,
            "recurrence": "weekly",
        },
    }
    event = mock_events.get(event_id)
    if not event:
        return {"status": "error", "message": f"Event not found: {event_id}"}
    return {"status": "success", "event": event}


@mcp.tool()
def create_event(
    title: str,
    start_time: str,
    end_time: str,
    attendees: str = "",
    location: str = "",
    description: str = "",
) -> dict:
    """Create a new calendar event.

    Args:
        title: Event title
        start_time: Start time in ISO format (e.g. 2026-03-13T09:00:00)
        end_time: End time in ISO format
        attendees: Comma-separated attendee names or emails
        location: Event location or meeting link
        description: Event description

    Returns:
        Dictionary with created event details
    """
    event_id = f"evt-{datetime.now().strftime('%H%M%S')}"
    attendee_list = [a.strip() for a in attendees.split(",") if a.strip()] if attendees else []
    return {
        "status": "success",
        "message": "Event created successfully",
        "event": {
            "event_id": event_id,
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "attendees": attendee_list,
            "location": location,
            "description": description,
            "status": "confirmed",
        },
    }


@mcp.tool()
def update_event(
    event_id: str,
    title: str = "",
    start_time: str = "",
    end_time: str = "",
    attendees: str = "",
    location: str = "",
) -> dict:
    """Update an existing calendar event.

    Args:
        event_id: The event identifier to update
        title: New title (leave empty to keep current)
        start_time: New start time in ISO format (leave empty to keep current)
        end_time: New end time in ISO format (leave empty to keep current)
        attendees: New comma-separated attendee list (leave empty to keep current)
        location: New location (leave empty to keep current)

    Returns:
        Dictionary with update confirmation
    """
    updates = {}
    if title:
        updates["title"] = title
    if start_time:
        updates["start_time"] = start_time
    if end_time:
        updates["end_time"] = end_time
    if attendees:
        updates["attendees"] = [a.strip() for a in attendees.split(",")]
    if location:
        updates["location"] = location

    return {
        "status": "success",
        "message": f"Event {event_id} updated successfully",
        "event_id": event_id,
        "updates_applied": updates,
    }


@mcp.tool()
def delete_event(event_id: str) -> dict:
    """Delete a calendar event.

    Args:
        event_id: The event identifier to delete

    Returns:
        Dictionary with deletion confirmation
    """
    return {
        "status": "success",
        "message": f"Event {event_id} deleted successfully",
        "event_id": event_id,
    }


@mcp.tool()
def check_availability(date: str, attendees: str = "") -> dict:
    """Check availability / free-busy status for a given date.

    Args:
        date: Date to check in ISO format (e.g. 2026-03-13)
        attendees: Comma-separated attendee names to check (leave empty for self only)

    Returns:
        Dictionary with free/busy time slots
    """
    try:
        day = datetime.fromisoformat(date)
    except ValueError:
        day = _today()

    attendee_list = [a.strip() for a in attendees.split(",") if a.strip()] if attendees else ["me"]

    free_slots = [
        {"start": day.replace(hour=8, minute=0).isoformat(), "end": day.replace(hour=9, minute=0).isoformat()},
        {"start": day.replace(hour=10, minute=0).isoformat(), "end": day.replace(hour=11, minute=0).isoformat()},
        {"start": day.replace(hour=12, minute=0).isoformat(), "end": day.replace(hour=14, minute=0).isoformat()},
        {"start": day.replace(hour=15, minute=30).isoformat(), "end": day.replace(hour=16, minute=0).isoformat()},
    ]
    busy_slots = [
        {"start": day.replace(hour=9, minute=0).isoformat(), "end": day.replace(hour=10, minute=0).isoformat(), "event": "Sprint Planning"},
        {"start": day.replace(hour=11, minute=0).isoformat(), "end": day.replace(hour=11, minute=30).isoformat(), "event": "1:1 with Nagy Anna"},
        {"start": day.replace(hour=14, minute=0).isoformat(), "end": day.replace(hour=15, minute=30).isoformat(), "event": "Client Review - Acme Corp"},
        {"start": day.replace(hour=16, minute=0).isoformat(), "end": day.replace(hour=17, minute=0).isoformat(), "event": "Team Retrospective"},
    ]

    return {
        "status": "success",
        "date": date,
        "checked_for": attendee_list,
        "free_slots": free_slots,
        "busy_slots": busy_slots,
    }


@mcp.tool()
def find_conflicts(start_time: str, end_time: str) -> dict:
    """Find scheduling conflicts for a proposed time range.

    Args:
        start_time: Proposed start time in ISO format
        end_time: Proposed end time in ISO format

    Returns:
        Dictionary with any conflicting events
    """
    try:
        proposed_start = datetime.fromisoformat(start_time)
    except ValueError:
        return {"status": "error", "message": "Invalid start_time format"}

    # Mock: return a conflict if the time overlaps with 9-10 AM
    conflicts = []
    if proposed_start.hour < 10 and proposed_start.hour >= 8:
        conflicts.append({
            "event_id": "evt-001",
            "title": "Sprint Planning",
            "start_time": proposed_start.replace(hour=9, minute=0).isoformat(),
            "end_time": proposed_start.replace(hour=10, minute=0).isoformat(),
            "overlap_minutes": 30,
        })

    return {
        "status": "success",
        "proposed": {"start_time": start_time, "end_time": end_time},
        "has_conflicts": len(conflicts) > 0,
        "conflicts": conflicts,
        "suggestion": "No conflicts found" if not conflicts else "Consider scheduling after 10:00",
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
