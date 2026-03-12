"""MCP server for email_agent - email management tools with mock data."""

from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("EmailServer")


def _now() -> datetime:
    return datetime.now()


def _mock_inbox() -> list[dict]:
    """Generate realistic mock inbox emails."""
    now = _now()
    return [
        {
            "email_id": "mail-001",
            "from": "Tóth László <toth.laszlo@company.hu>",
            "to": "me",
            "subject": "Q1 Deliverables - Action Required",
            "date": (now - timedelta(hours=2)).isoformat(),
            "snippet": "Hi, please review the attached Q1 report and confirm the numbers by EOD...",
            "labels": ["inbox", "important"],
            "unread": True,
            "has_attachments": True,
            "priority": "high",
        },
        {
            "email_id": "mail-002",
            "from": "Nagy Anna <nagy.anna@company.hu>",
            "to": "me",
            "subject": "Re: Sprint Planning Agenda",
            "date": (now - timedelta(hours=5)).isoformat(),
            "snippet": "I've added the new feature requests to the agenda. Can you also include the tech debt items?",
            "labels": ["inbox"],
            "unread": True,
            "has_attachments": False,
            "priority": "medium",
        },
        {
            "email_id": "mail-003",
            "from": "John Smith <john.smith@acmecorp.com>",
            "to": "me",
            "subject": "Meeting Follow-up: Partnership Discussion",
            "date": (now - timedelta(days=1)).isoformat(),
            "snippet": "Thank you for the productive meeting yesterday. As discussed, here are the next steps...",
            "labels": ["inbox", "clients"],
            "unread": False,
            "has_attachments": True,
            "priority": "high",
        },
        {
            "email_id": "mail-004",
            "from": "HR Department <hr@company.hu>",
            "to": "all-staff",
            "subject": "Reminder: Annual Review Submissions Due Friday",
            "date": (now - timedelta(days=1, hours=3)).isoformat(),
            "snippet": "This is a reminder that all annual self-review forms must be submitted by Friday...",
            "labels": ["inbox", "hr"],
            "unread": True,
            "has_attachments": False,
            "priority": "medium",
        },
        {
            "email_id": "mail-005",
            "from": "Kovács Péter <kovacs.peter@company.hu>",
            "to": "me",
            "subject": "Quick question about the API integration",
            "date": (now - timedelta(days=2)).isoformat(),
            "snippet": "Hey, I noticed the API endpoint for the new feature is returning 500 errors. Can you check?",
            "labels": ["inbox", "dev"],
            "unread": False,
            "has_attachments": False,
            "priority": "high",
        },
    ]


@mcp.tool()
def list_emails(folder: str = "inbox", limit: int = 20, unread_only: bool = False) -> dict:
    """List emails from a mail folder.

    Args:
        folder: Mail folder to list (inbox, sent, drafts, trash)
        limit: Maximum number of emails to return
        unread_only: If true, only return unread emails

    Returns:
        Dictionary with email list
    """
    emails = _mock_inbox()
    if unread_only:
        emails = [e for e in emails if e.get("unread", False)]
    emails = emails[:limit]
    return {
        "status": "success",
        "folder": folder,
        "emails": emails,
        "total_count": len(emails),
        "unread_count": sum(1 for e in emails if e.get("unread", False)),
    }


@mcp.tool()
def get_email(email_id: str) -> dict:
    """Read the full content of a specific email.

    Args:
        email_id: The email identifier (e.g. mail-001)

    Returns:
        Dictionary with full email content
    """
    now = _now()
    mock_emails = {
        "mail-001": {
            "email_id": "mail-001",
            "from": "Tóth László <toth.laszlo@company.hu>",
            "to": ["me"],
            "cc": ["Nagy Anna <nagy.anna@company.hu>"],
            "subject": "Q1 Deliverables - Action Required",
            "date": (now - timedelta(hours=2)).isoformat(),
            "body": (
                "Hi,\n\n"
                "Please review the attached Q1 deliverables report and confirm the numbers by end of day today.\n\n"
                "Key points that need your sign-off:\n"
                "1. Revenue figures for the Platform division\n"
                "2. Customer acquisition costs\n"
                "3. Sprint velocity metrics\n\n"
                "The board presentation is scheduled for Thursday, so we need final numbers by Wednesday morning.\n\n"
                "Thanks,\nLászló"
            ),
            "attachments": [
                {"name": "Q1_Deliverables_Report.xlsx", "size": "2.4 MB"},
                {"name": "Sprint_Metrics_Q1.pdf", "size": "850 KB"},
            ],
            "labels": ["inbox", "important"],
            "thread_id": "thread-001",
            "thread_count": 3,
        },
        "mail-002": {
            "email_id": "mail-002",
            "from": "Nagy Anna <nagy.anna@company.hu>",
            "to": ["me"],
            "cc": [],
            "subject": "Re: Sprint Planning Agenda",
            "date": (now - timedelta(hours=5)).isoformat(),
            "body": (
                "Hi,\n\n"
                "I've added the new feature requests to the agenda. Can you also include the tech debt items?\n\n"
                "Here's what I have so far:\n"
                "1. Feature: User dashboard redesign (45 min)\n"
                "2. Feature: API rate limiting (30 min)\n"
                "3. Bug triage from last sprint (20 min)\n\n"
                "I think we should also schedule a separate meeting for the tech debt discussion — "
                "maybe Thursday at 2 PM? Let me know if that works.\n\n"
                "Thanks,\nAnna"
            ),
            "attachments": [],
            "labels": ["inbox"],
            "thread_id": "thread-002",
            "thread_count": 5,
        },
        "mail-003": {
            "email_id": "mail-003",
            "from": "John Smith <john.smith@acmecorp.com>",
            "to": ["me"],
            "cc": ["Szabó Gábor <szabo.gabor@company.hu>"],
            "subject": "Meeting Follow-up: Partnership Discussion",
            "date": (now - timedelta(days=1)).isoformat(),
            "body": (
                "Hi,\n\n"
                "Thank you for the productive meeting yesterday. As discussed, here are the next steps:\n\n"
                "1. Technical integration review — let's schedule a call for next Tuesday at 10 AM (CET) "
                "with your API team and our integration engineers.\n"
                "   Attendees: you, Szabó Gábor, myself, and Sarah Chen from our side.\n\n"
                "2. Contract review meeting — our legal team proposed next Wednesday at 3 PM (CET).\n"
                "   Attendees: you, John Smith, Maria Lopez (AcmeCorp Legal).\n\n"
                "3. Pilot kickoff — targeting the week of the 24th, exact date TBD.\n\n"
                "Could you confirm these times work on your end?\n\n"
                "Best regards,\nJohn Smith\nVP Partnerships, AcmeCorp"
            ),
            "attachments": [
                {"name": "Partnership_Proposal_v2.pdf", "size": "1.2 MB"},
            ],
            "labels": ["inbox", "clients"],
            "thread_id": "thread-003",
            "thread_count": 2,
        },
        "mail-004": {
            "email_id": "mail-004",
            "from": "HR Department <hr@company.hu>",
            "to": ["all-staff"],
            "cc": [],
            "subject": "Reminder: Annual Review Submissions Due Friday",
            "date": (now - timedelta(days=1, hours=3)).isoformat(),
            "body": (
                "Dear Team,\n\n"
                "This is a reminder that all annual self-review forms must be submitted by Friday, end of day.\n\n"
                "Please complete the following:\n"
                "1. Self-assessment form in the HR portal\n"
                "2. Peer review nominations (minimum 3)\n"
                "3. Goals for next quarter\n\n"
                "Your manager review meetings will be scheduled for the following week. "
                "You will receive a calendar invite once your submission is confirmed.\n\n"
                "Best regards,\nHR Department"
            ),
            "attachments": [],
            "labels": ["inbox", "hr"],
            "thread_id": "thread-004",
            "thread_count": 1,
        },
        "mail-005": {
            "email_id": "mail-005",
            "from": "Kovács Péter <kovacs.peter@company.hu>",
            "to": ["me"],
            "cc": [],
            "subject": "Quick question about the API integration",
            "date": (now - timedelta(days=2)).isoformat(),
            "body": (
                "Hey,\n\n"
                "I noticed the API endpoint for the new feature is returning 500 errors intermittently.\n\n"
                "Can you check the logs when you get a chance? I think it might be related to the "
                "database connection pool changes we made last week.\n\n"
                "Also — can we set up a quick 30-minute debugging session tomorrow morning? "
                "Maybe around 9:30 AM? I'll share my screen and walk you through what I'm seeing.\n\n"
                "Thanks,\nPéter"
            ),
            "attachments": [],
            "labels": ["inbox", "dev"],
            "thread_id": "thread-005",
            "thread_count": 1,
        },
    }
    email = mock_emails.get(email_id)
    if not email:
        return {"status": "error", "message": f"Email not found: {email_id}"}
    return {"status": "success", "email": email}


@mcp.tool()
def search_emails(query: str, limit: int = 10) -> dict:
    """Search emails by query.

    Args:
        query: Search query (searches subject, sender, and body)
        limit: Maximum results to return

    Returns:
        Dictionary with matching emails
    """
    all_emails = _mock_inbox()
    query_lower = query.lower()
    # Support OR-separated terms (e.g. "meeting OR találkozó")
    terms = [t.strip() for t in query_lower.split(" or ") if t.strip()] if " or " in query_lower else [query_lower]
    results = [
        e for e in all_emails
        if any(
            term in e["subject"].lower()
            or term in e["from"].lower()
            or term in e["snippet"].lower()
            for term in terms
        )
    ]
    return {
        "status": "success",
        "query": query,
        "results": results[:limit],
        "result_count": len(results),
    }


@mcp.tool()
def send_email(to: str, subject: str, body: str, cc: str = "", reply_to_id: str = "") -> dict:
    """Send an email.

    Args:
        to: Recipient email address(es), comma-separated
        subject: Email subject
        body: Email body text
        cc: CC recipients, comma-separated (optional)
        reply_to_id: Email ID to reply to (optional, for threading)

    Returns:
        Dictionary with send confirmation
    """
    return {
        "status": "success",
        "message": "Email sent successfully",
        "details": {
            "to": [t.strip() for t in to.split(",")],
            "cc": [c.strip() for c in cc.split(",") if c.strip()] if cc else [],
            "subject": subject,
            "reply_to": reply_to_id or None,
            "sent_at": _now().isoformat(),
        },
    }


@mcp.tool()
def draft_reply(email_id: str, tone: str = "professional") -> dict:
    """Generate a reply draft for an email.

    Args:
        email_id: The email ID to reply to
        tone: Desired tone (professional, casual, formal)

    Returns:
        Dictionary with draft reply content
    """
    drafts = {
        "mail-001": {
            "subject": "Re: Q1 Deliverables - Action Required",
            "to": "Tóth László <toth.laszlo@company.hu>",
            "body": (
                "Hi László,\n\n"
                "Thanks for sending these over. I've reviewed the Q1 report and the numbers look good.\n\n"
                "A few notes:\n"
                "- Revenue figures for Platform division: confirmed\n"
                "- Customer acquisition costs: I'd like to double-check the March numbers, will get back to you by EOD\n"
                "- Sprint velocity metrics: confirmed\n\n"
                "I'll have the final sign-off ready before the Wednesday morning deadline.\n\n"
                "Best regards"
            ),
        },
    }
    draft = drafts.get(email_id, {
        "subject": f"Re: [reply to {email_id}]",
        "to": "sender",
        "body": "Thank you for your email. I will review and get back to you shortly.",
    })
    return {
        "status": "success",
        "draft": draft,
        "tone": tone,
        "note": "This is a draft. Please review before sending.",
    }


@mcp.tool()
def label_email(email_id: str, labels: str) -> dict:
    """Apply labels/categories to an email.

    Args:
        email_id: The email identifier
        labels: Comma-separated labels to apply (e.g. "important, follow-up")

    Returns:
        Dictionary with label confirmation
    """
    label_list = [l.strip() for l in labels.split(",") if l.strip()]
    return {
        "status": "success",
        "message": f"Labels applied to {email_id}",
        "email_id": email_id,
        "labels": label_list,
    }


@mcp.tool()
def get_follow_ups() -> dict:
    """Get emails that need follow-up responses.

    Returns:
        Dictionary with emails awaiting follow-up
    """
    now = _now()
    return {
        "status": "success",
        "follow_ups": [
            {
                "email_id": "mail-003",
                "from": "John Smith <john.smith@acmecorp.com>",
                "subject": "Meeting Follow-up: Partnership Discussion",
                "sent_date": (now - timedelta(days=1)).isoformat(),
                "days_waiting": 1,
                "urgency": "high",
                "reason": "Client email with action items, no reply sent yet",
            },
            {
                "email_id": "mail-005",
                "from": "Kovács Péter <kovacs.peter@company.hu>",
                "subject": "Quick question about the API integration",
                "sent_date": (now - timedelta(days=2)).isoformat(),
                "days_waiting": 2,
                "urgency": "medium",
                "reason": "Technical question from team member, awaiting response",
            },
        ],
        "total_follow_ups": 2,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
