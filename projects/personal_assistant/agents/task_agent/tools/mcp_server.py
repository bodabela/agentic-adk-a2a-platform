"""MCP server for task_agent - task and project management tools with mock data."""

from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("TaskProjectServer")


def _now() -> datetime:
    return datetime.now()


def _today() -> datetime:
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


def _mock_tasks() -> list[dict]:
    """Generate realistic mock tasks."""
    today = _today()
    return [
        {
            "task_id": "PROJ-101",
            "title": "Implement API v2 rate limiting",
            "description": "Add configurable rate limiting to all v2 API endpoints.  Must follow RFC 6585 (RateLimit-* headers).  Required by Acme Corp partnership (doc-003).  Blocks PROJ-105 (monitoring dashboards).",
            "project": "Platform",
            "status": "in_progress",
            "priority": "high",
            "assignee": "me",
            "due_date": (today + timedelta(days=3)).strftime("%Y-%m-%d"),
            "labels": ["backend", "api"],
            "created": (today - timedelta(days=7)).strftime("%Y-%m-%d"),
            "sprint": "Sprint 24",
        },
        {
            "task_id": "PROJ-102",
            "title": "Fix authentication token refresh bug",
            "description": "Users report intermittent 401 errors when tokens expire during long sessions.  Root cause: race condition in token refresh + DB connection pool exhaustion (see #incidents latency spike and mail-005).  Blocks Acme Corp certification suite.",
            "project": "Platform",
            "status": "open",
            "priority": "critical",
            "assignee": "me",
            "due_date": (today + timedelta(days=1)).strftime("%Y-%m-%d"),
            "labels": ["backend", "bug", "auth"],
            "created": (today - timedelta(days=2)).strftime("%Y-%m-%d"),
            "sprint": "Sprint 24",
        },
        {
            "task_id": "PROJ-103",
            "title": "Write SDK documentation for Python client",
            "description": "Create comprehensive docs for the new Python SDK including examples and tutorials.  Use API v2 staging (deployed by Horváth Dávid) for live examples.  See API v2 Design Document on Confluence (doc-006).",
            "project": "Platform",
            "status": "open",
            "priority": "medium",
            "assignee": "me",
            "due_date": (today + timedelta(days=10)).strftime("%Y-%m-%d"),
            "labels": ["docs", "sdk"],
            "created": (today - timedelta(days=5)).strftime("%Y-%m-%d"),
            "sprint": "Sprint 24",
        },
        {
            "task_id": "PROJ-104",
            "title": "Review Acme Corp integration PR",
            "description": "Code review for the Acme Corp webhook integration PR.  HMAC-SHA256 signing per Acme requirements (doc-003).  John Smith needs this before pilot kickoff (mail-003).  Technical review next Tuesday.",
            "project": "Partnerships",
            "status": "open",
            "priority": "high",
            "assignee": "me",
            "due_date": (today + timedelta(days=2)).strftime("%Y-%m-%d"),
            "labels": ["review", "acme"],
            "created": (today - timedelta(days=1)).strftime("%Y-%m-%d"),
            "sprint": "Sprint 24",
        },
        {
            "task_id": "PROJ-105",
            "title": "Set up monitoring dashboards for v2 API",
            "description": "Create Grafana dashboards for API v2 metrics: latency (p50/p95/p99), error rates, throughput, connection pool utilisation.  The #incidents latency spike proves we need this urgently.  Blocked by PROJ-101 (rate limiting).",
            "project": "Platform",
            "status": "blocked",
            "priority": "medium",
            "assignee": "Horváth Dávid",
            "due_date": (today + timedelta(days=5)).strftime("%Y-%m-%d"),
            "labels": ["infra", "monitoring"],
            "created": (today - timedelta(days=4)).strftime("%Y-%m-%d"),
            "sprint": "Sprint 24",
            "blocked_by": "PROJ-101",
        },
    ]


@mcp.tool()
def list_tasks(project: str = "", status: str = "", assignee: str = "me", limit: int = 20) -> dict:
    """List tasks with optional filters.

    Args:
        project: Filter by project name (leave empty for all)
        status: Filter by status (open, in_progress, blocked, done)
        assignee: Filter by assignee (default: me)
        limit: Maximum number of tasks to return

    Returns:
        Dictionary with filtered task list
    """
    tasks = _mock_tasks()
    if project:
        tasks = [t for t in tasks if t["project"].lower() == project.lower()]
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    if assignee and assignee != "all":
        tasks = [t for t in tasks if t["assignee"] == assignee]

    return {
        "status": "success",
        "filters": {"project": project or "all", "status": status or "all", "assignee": assignee},
        "tasks": tasks[:limit],
        "total_count": len(tasks),
    }


@mcp.tool()
def get_task(task_id: str) -> dict:
    """Get detailed information about a specific task.

    Args:
        task_id: The task identifier (e.g. PROJ-101)

    Returns:
        Dictionary with task details including comments and history
    """
    now = _now()
    tasks = {t["task_id"]: t for t in _mock_tasks()}
    task = tasks.get(task_id)
    if not task:
        return {"status": "error", "message": f"Task not found: {task_id}"}

    # Task-specific comments that reference other agents' data
    task_comments = {
        "PROJ-101": [
            {
                "author": "Kovács Péter",
                "date": (now - timedelta(days=1)).isoformat(),
                "text": (
                    "Rate limiting middleware is in place, testing now.  "
                    "Kiss Márta's SDK PR #342 covers the client-side headers (see #platform-dev).  "
                    "Once this is done, Horváth Dávid can unblock PROJ-105 (dashboards).  "
                    "Acme Corp requires RFC 6585 compliance — see Technical Requirements doc (doc-003)."
                ),
            },
        ],
        "PROJ-102": [
            {
                "author": "Kovács Péter",
                "date": (now - timedelta(hours=2)).isoformat(),
                "text": (
                    "Root cause identified: race condition in token refresh when DB connection "
                    "pool is exhausted.  Same issue causing the latency spike in #incidents.  "
                    "Emailed details (mail-005).  Fix: implement single-flight refresh pattern "
                    "with TTL buffer.  ⚠️ Blocks Acme Corp certification (their suite tests "
                    "token refresh flows)."
                ),
            },
            {
                "author": "Nagy Anna",
                "date": (now - timedelta(hours=1)).isoformat(),
                "text": "Escalating to critical — this is blocking the Acme Corp pilot.  Added to Sprint Planning agenda (9 AM, evt-001).",
            },
        ],
        "PROJ-103": [
            {
                "author": "Horváth Dávid",
                "date": (now - timedelta(days=2)).isoformat(),
                "text": "I've pushed the API v2 staging deployment — you can use it as a reference for SDK examples.  See the API v2 Design Document on Confluence (doc-006).",
            },
        ],
        "PROJ-104": [
            {
                "author": "Varga Eszter",
                "date": (now - timedelta(hours=6)).isoformat(),
                "text": (
                    "John Smith confirmed this is required for the pilot kickoff (week of the 24th).  "
                    "See his follow-up email (mail-003) and the kickoff meeting notes (doc-005).  "
                    "Technical integration review is next Tuesday — need this reviewed before then."
                ),
            },
            {
                "author": "Szabó Gábor",
                "date": (now - timedelta(hours=3)).isoformat(),
                "text": "I'll set up the webhook test environment.  Needs HMAC-SHA256 signing per Acme's requirements (doc-003).",
            },
        ],
        "PROJ-105": [
            {
                "author": "Horváth Dávid",
                "date": (now - timedelta(hours=1)).isoformat(),
                "text": (
                    "Still blocked on PROJ-101.  The latency incident in #incidents proves "
                    "we need these dashboards urgently — pool utilisation alerts would have "
                    "caught the issue earlier.  Template ready: Grafana panels for p50/p95/p99 "
                    "latency, error rates, and connection pool metrics."
                ),
            },
        ],
    }
    task["comments"] = task_comments.get(task_id, [
        {
            "author": "Kovács Péter",
            "date": (now - timedelta(days=1)).isoformat(),
            "text": "Working on this.  Will update in #platform-dev when done.",
        },
    ])
    task["activity"] = [
        {"action": "created", "by": "Nagy Anna", "date": task["created"]},
        {"action": "assigned to me", "by": "Nagy Anna", "date": task["created"]},
        {"action": "status changed to " + task["status"], "by": "me", "date": (now - timedelta(days=1)).isoformat()},
    ]
    return {"status": "success", "task": task}


@mcp.tool()
def create_task(
    title: str,
    description: str = "",
    project: str = "Platform",
    priority: str = "medium",
    assignee: str = "me",
    due_date: str = "",
) -> dict:
    """Create a new task.

    Args:
        title: Task title
        description: Detailed task description
        project: Project name
        priority: Priority level (critical, high, medium, low)
        assignee: Person to assign to
        due_date: Due date in ISO format (YYYY-MM-DD)

    Returns:
        Dictionary with created task details
    """
    task_id = f"PROJ-{datetime.now().strftime('%H%M')}"
    return {
        "status": "success",
        "message": "Task created successfully",
        "task": {
            "task_id": task_id,
            "title": title,
            "description": description,
            "project": project,
            "priority": priority,
            "assignee": assignee,
            "due_date": due_date or (_today() + timedelta(days=7)).strftime("%Y-%m-%d"),
            "status": "open",
            "created": _now().isoformat(),
            "sprint": "Sprint 24",
        },
    }


@mcp.tool()
def update_task(task_id: str, status: str = "", priority: str = "", assignee: str = "") -> dict:
    """Update a task's status, priority, or assignee.

    Args:
        task_id: The task identifier to update
        status: New status (open, in_progress, blocked, done)
        priority: New priority (critical, high, medium, low)
        assignee: New assignee

    Returns:
        Dictionary with update confirmation
    """
    updates = {}
    if status:
        updates["status"] = status
    if priority:
        updates["priority"] = priority
    if assignee:
        updates["assignee"] = assignee

    return {
        "status": "success",
        "message": f"Task {task_id} updated successfully",
        "task_id": task_id,
        "updates_applied": updates,
    }


@mcp.tool()
def get_sprint_overview(project: str = "") -> dict:
    """Get current sprint overview with progress metrics.

    Args:
        project: Filter by project name (leave empty for all)

    Returns:
        Dictionary with sprint summary and metrics
    """
    return {
        "status": "success",
        "sprint": {
            "name": "Sprint 24",
            "start_date": (_today() - timedelta(days=5)).strftime("%Y-%m-%d"),
            "end_date": (_today() + timedelta(days=9)).strftime("%Y-%m-%d"),
            "days_remaining": 9,
            "progress": {
                "total_tasks": 12,
                "done": 4,
                "in_progress": 3,
                "open": 4,
                "blocked": 1,
                "completion_percentage": 33,
            },
            "at_risk": [
                {
                    "task_id": "PROJ-102",
                    "title": "Fix authentication token refresh bug",
                    "reason": "Critical priority, due tomorrow",
                },
            ],
            "blocked_items": [
                {
                    "task_id": "PROJ-105",
                    "title": "Set up monitoring dashboards for v2 API",
                    "blocked_by": "PROJ-101",
                },
            ],
            "velocity": {
                "current_sprint": 15,
                "average_3_sprints": 18,
                "trend": "below average",
            },
        },
    }


@mcp.tool()
def get_my_next_tasks() -> dict:
    """Get a prioritized list of the user's upcoming tasks.

    Returns:
        Dictionary with prioritized task list and recommendations
    """
    tasks = [t for t in _mock_tasks() if t["assignee"] == "me" and t["status"] != "done"]
    tasks.sort(key=lambda t: (
        {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(t["priority"], 4),
        t["due_date"],
    ))

    return {
        "status": "success",
        "next_tasks": tasks,
        "recommendation": (
            "Focus on PROJ-102 (critical auth bug, due tomorrow) — it's causing the "
            "#incidents latency spike and blocks Acme Corp certification.  "
            "Then PROJ-104 (Acme webhook PR review, due in 2 days) — John Smith needs "
            "this before the technical integration review next Tuesday (see mail-003).  "
            "PROJ-101 (rate limiting) is in progress — completing it unblocks PROJ-105 "
            "(monitoring dashboards, Horváth Dávid)."
        ),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
