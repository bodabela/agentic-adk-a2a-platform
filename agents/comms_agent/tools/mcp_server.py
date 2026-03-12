"""MCP server for comms_agent - communication management tools with mock data."""

from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("CommunicationServer")


def _now() -> datetime:
    return datetime.now()


@mcp.tool()
def list_channels() -> dict:
    """List available communication channels across platforms.

    Returns:
        Dictionary with channel list and unread counts
    """
    return {
        "status": "success",
        "channels": [
            {"channel_id": "ch-001", "name": "#general", "platform": "slack", "unread": 12, "mentions": 0},
            {"channel_id": "ch-002", "name": "#platform-dev", "platform": "slack", "unread": 8, "mentions": 3},
            {"channel_id": "ch-003", "name": "#acme-partnership", "platform": "slack", "unread": 5, "mentions": 1},
            {"channel_id": "ch-004", "name": "Platform Team", "platform": "teams", "unread": 3, "mentions": 0},
            {"channel_id": "ch-005", "name": "#incidents", "platform": "slack", "unread": 2, "mentions": 2},
            {"channel_id": "ch-006", "name": "#random", "platform": "slack", "unread": 25, "mentions": 0},
        ],
        "total_unread": 55,
        "total_mentions": 6,
    }


@mcp.tool()
def get_channel_messages(channel_id: str, limit: int = 20, since: str = "") -> dict:
    """Get recent messages from a specific channel.

    Args:
        channel_id: The channel identifier (e.g. ch-001)
        limit: Maximum number of messages to return
        since: Only return messages after this ISO timestamp

    Returns:
        Dictionary with channel messages
    """
    now = _now()
    mock_messages = {
        "ch-002": [
            {
                "message_id": "msg-001",
                "author": "Horváth Dávid",
                "timestamp": (now - timedelta(hours=1)).isoformat(),
                "text": (
                    "The API v2 staging deployment is complete.  @me can you run the "
                    "integration tests?  We need this green before the Acme Corp review "
                    "this afternoon (evt-003).  My PROJ-105 dashboards are still blocked "
                    "on PROJ-101 (rate limiting)."
                ),
                "is_mention": True,
                "thread_count": 2,
            },
            {
                "message_id": "msg-002",
                "author": "Kiss Márta",
                "timestamp": (now - timedelta(hours=2)).isoformat(),
                "text": (
                    "I've updated the SDK client to handle the new rate limit headers "
                    "(RFC 6585).  PR #342 is up — this covers the client side of PROJ-101.  "
                    "Also added Retry-After support for 429 responses."
                ),
                "is_mention": False,
                "thread_count": 5,
            },
            {
                "message_id": "msg-003",
                "author": "Szabó Gábor",
                "timestamp": (now - timedelta(hours=3)).isoformat(),
                "text": (
                    "FYI: The CI pipeline for the main branch is green again after the "
                    "flaky test fix.  Ready for Sprint Planning at 9 AM.  "
                    "Also: I'll attend the Acme Corp technical integration review next "
                    "Tuesday as John Smith requested (see his email)."
                ),
                "is_mention": False,
                "thread_count": 0,
            },
        ],
        "ch-003": [
            {
                "message_id": "msg-020",
                "author": "Varga Eszter",
                "timestamp": (now - timedelta(hours=4)).isoformat(),
                "text": (
                    "@me the Acme team confirmed the technical review for Thursday.  "
                    "John Smith and Sarah Chen will join from their side.  "
                    "Can you prepare the demo?  I've updated the kickoff meeting notes "
                    "on Notion (doc-005)."
                ),
                "is_mention": True,
                "thread_count": 3,
            },
            {
                "message_id": "msg-021",
                "author": "Tóth László",
                "timestamp": (now - timedelta(hours=3, minutes=30)).isoformat(),
                "text": (
                    "I've updated the Technical Requirements doc on Confluence (doc-003) "
                    "with the webhook specs.  Please review before the Client Review at "
                    "2 PM today.  Also — I need your sign-off on Q1 numbers (check my email)."
                ),
                "is_mention": False,
                "thread_count": 1,
            },
        ],
        "ch-005": [
            {
                "message_id": "msg-010",
                "author": "AlertBot",
                "timestamp": (now - timedelta(minutes=30)).isoformat(),
                "text": (
                    "🔴 ALERT: API latency spike detected on production (p99 > 2 s).  "
                    "@me @Kovács Péter please investigate.  Possibly related to PROJ-102 "
                    "(auth token refresh bug)."
                ),
                "is_mention": True,
                "thread_count": 4,
            },
            {
                "message_id": "msg-011",
                "author": "Kovács Péter",
                "timestamp": (now - timedelta(minutes=20)).isoformat(),
                "text": (
                    "Looking into it.  Seems related to the database connection pool "
                    "changes we made last week — same root cause I emailed about "
                    "(mail-005).  Scaling up the pool now.  Will need to discuss in "
                    "Sprint Planning and schedule a post-incident review."
                ),
                "is_mention": False,
                "thread_count": 0,
            },
            {
                "message_id": "msg-012",
                "author": "Horváth Dávid",
                "timestamp": (now - timedelta(minutes=10)).isoformat(),
                "text": (
                    "This is also why we need PROJ-105 (monitoring dashboards) unblocked.  "
                    "Once PROJ-101 rate limiting is done I can set up proper Grafana "
                    "alerts for pool utilisation.  Adding this to the retro agenda."
                ),
                "is_mention": False,
                "thread_count": 0,
            },
        ],
    }

    messages = mock_messages.get(channel_id, [
        {
            "message_id": "msg-default",
            "author": "System",
            "timestamp": now.isoformat(),
            "text": "No recent messages in this channel.",
            "is_mention": False,
            "thread_count": 0,
        },
    ])

    return {
        "status": "success",
        "channel_id": channel_id,
        "messages": messages[:limit],
        "message_count": len(messages),
    }


@mcp.tool()
def get_important_messages(since: str = "") -> dict:
    """Get important messages across all channels (mentions, action items, urgent).

    Args:
        since: Only return messages after this ISO timestamp (default: last 24 hours)

    Returns:
        Dictionary with important messages grouped by urgency
    """
    now = _now()
    return {
        "status": "success",
        "important_messages": {
            "urgent": [
                {
                    "message_id": "msg-010",
                    "channel": "#incidents",
                    "author": "AlertBot",
                    "timestamp": (now - timedelta(minutes=30)).isoformat(),
                    "text": "🔴 ALERT: API latency spike (p99 > 2 s).  Possibly related to PROJ-102 (auth token refresh bug).  Kovács Péter investigating — DB connection pool.",
                    "reason": "Incident alert with direct mention — linked to PROJ-102 and Péter's email (mail-005)",
                },
            ],
            "action_required": [
                {
                    "message_id": "msg-001",
                    "channel": "#platform-dev",
                    "author": "Horváth Dávid",
                    "timestamp": (now - timedelta(hours=1)).isoformat(),
                    "text": "Run integration tests on v2 staging — needed before Acme Corp review (evt-003) this afternoon.  PROJ-105 dashboards still blocked on PROJ-101.",
                    "reason": "Direct mention with action request — blocks Acme Corp client review",
                },
            ],
            "mentions": [
                {
                    "message_id": "msg-020",
                    "channel": "#acme-partnership",
                    "author": "Varga Eszter",
                    "timestamp": (now - timedelta(hours=4)).isoformat(),
                    "text": "Acme team confirmed technical review for Thursday.  John Smith & Sarah Chen attending.  Prepare demo — kickoff notes on Notion (doc-005).",
                    "reason": "Direct mention in partnership channel — follow-up to John Smith's email (mail-003)",
                },
            ],
        },
        "total_important": 3,
    }


@mcp.tool()
def send_message(channel_id: str, message: str, thread_id: str = "") -> dict:
    """Send a message to a channel or thread.

    Args:
        channel_id: Target channel identifier
        message: Message text to send
        thread_id: Thread ID to reply in (optional, for thread replies)

    Returns:
        Dictionary with send confirmation
    """
    return {
        "status": "success",
        "message": "Message sent successfully",
        "details": {
            "channel_id": channel_id,
            "thread_id": thread_id or None,
            "sent_at": _now().isoformat(),
            "preview": message[:100] + "..." if len(message) > 100 else message,
        },
    }


@mcp.tool()
def summarize_channel(channel_id: str, since: str = "") -> dict:
    """Get an AI-generated summary of recent channel activity.

    Args:
        channel_id: The channel to summarize
        since: Summarize messages after this ISO timestamp (default: last 24 hours)

    Returns:
        Dictionary with channel summary
    """
    summaries = {
        "ch-002": {
            "channel": "#platform-dev",
            "period": "last 24 hours",
            "summary": (
                "Key updates in #platform-dev:\n"
                "1. API v2 staging deployment completed (Horváth Dávid) — needs integration tests before Acme Corp review (evt-003)\n"
                "2. SDK client updated with RFC 6585 rate limit headers — PR #342 (Kiss Márta), covers client side of PROJ-101\n"
                "3. CI pipeline green again after flaky test fix (Szabó Gábor)\n"
                "4. PROJ-105 (monitoring dashboards) still blocked on PROJ-101 (rate limiting)"
            ),
            "action_items": [
                "Run integration tests on v2 staging before Acme Corp review at 2 PM (assigned to you)",
                "Review PR #342 for SDK rate limit headers (Kiss Márta)",
            ],
            "decisions": [
                "Rate limit headers will follow RFC 6585 standard",
                "Szabó Gábor to attend Acme Corp technical integration review next Tuesday",
            ],
            "message_count": 15,
            "active_participants": 5,
        },
        "ch-005": {
            "channel": "#incidents",
            "period": "last 24 hours",
            "summary": (
                "Active incident in #incidents:\n"
                "1. API latency spike detected (p99 > 2 s) — 30 minutes ago, likely related to PROJ-102\n"
                "2. Root cause: database connection pool exhaustion (same issue Kovács Péter emailed about — mail-005)\n"
                "3. Kovács Péter scaling up the pool; will discuss at Sprint Planning (9 AM)\n"
                "4. Horváth Dávid notes PROJ-105 (Grafana dashboards) would have caught this — blocked on PROJ-101"
            ),
            "action_items": [
                "Monitor API latency after connection pool scaling",
                "Post-incident review to be scheduled (add to retro agenda)",
                "Prioritise PROJ-101 to unblock PROJ-105 monitoring dashboards",
            ],
            "decisions": [],
            "message_count": 8,
            "active_participants": 3,
        },
    }

    summary = summaries.get(channel_id, {
        "channel": channel_id,
        "period": "last 24 hours",
        "summary": "No significant activity in this channel recently.",
        "action_items": [],
        "decisions": [],
        "message_count": 0,
        "active_participants": 0,
    })

    return {"status": "success", "channel_summary": summary}


if __name__ == "__main__":
    mcp.run(transport="stdio")
