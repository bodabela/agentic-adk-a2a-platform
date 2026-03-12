"""MCP server for document_agent - document management tools with mock data."""

from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("DocumentServer")


def _now() -> datetime:
    return datetime.now()


@mcp.tool()
def search_documents(query: str, source: str = "all", limit: int = 10) -> dict:
    """Search for documents across connected platforms.

    Args:
        query: Search query (semantic search across titles and content)
        source: Filter by source platform (all, google_drive, notion, confluence)
        limit: Maximum number of results

    Returns:
        Dictionary with matching documents
    """
    now = _now()
    results = [
        {
            "document_id": "doc-001",
            "title": "Q1 Platform Strategy",
            "source": "google_drive",
            "type": "document",
            "last_modified": (now - timedelta(days=3)).isoformat(),
            "modified_by": "Kovács Péter",
            "snippet": "Strategic priorities for Q1 include expanding the API platform, improving developer experience...",
            "relevance_score": 0.95,
            "url": "https://docs.google.com/document/d/abc123",
        },
        {
            "document_id": "doc-002",
            "title": "Sprint 23 Retrospective Notes",
            "source": "notion",
            "type": "page",
            "last_modified": (now - timedelta(days=5)).isoformat(),
            "modified_by": "Nagy Anna",
            "snippet": "What went well: Delivery on time, good collaboration. What to improve: Testing coverage, documentation...",
            "relevance_score": 0.82,
            "url": "https://notion.so/sprint-23-retro",
        },
        {
            "document_id": "doc-003",
            "title": "Acme Corp Partnership - Technical Requirements",
            "source": "confluence",
            "type": "page",
            "last_modified": (now - timedelta(days=7)).isoformat(),
            "modified_by": "Tóth László",
            "snippet": "Integration requirements: REST API endpoints, OAuth 2.0 authentication, webhook notifications...",
            "relevance_score": 0.78,
            "url": "https://company.atlassian.net/wiki/acme-requirements",
        },
        {
            "document_id": "doc-004",
            "title": "Team Onboarding Guide",
            "source": "google_drive",
            "type": "document",
            "last_modified": (now - timedelta(days=30)).isoformat(),
            "modified_by": "Szabó Gábor",
            "snippet": "Welcome to the team! This guide covers development setup, coding standards, PR review process...",
            "relevance_score": 0.65,
            "url": "https://docs.google.com/document/d/def456",
        },
    ]

    if source != "all":
        results = [r for r in results if r["source"] == source]

    return {
        "status": "success",
        "query": query,
        "source_filter": source,
        "results": results[:limit],
        "result_count": min(len(results), limit),
    }


@mcp.tool()
def get_document(document_id: str) -> dict:
    """Retrieve the full content of a document.

    Args:
        document_id: The document identifier (e.g. doc-001)

    Returns:
        Dictionary with full document content
    """
    now = _now()
    mock_docs = {
        "doc-001": {
            "document_id": "doc-001",
            "title": "Q1 Platform Strategy",
            "source": "google_drive",
            "content": (
                "# Q1 Platform Strategy\n\n"
                "## Executive Summary\n"
                "Our Q1 priorities focus on three key areas: API platform expansion, "
                "developer experience improvements, and strategic partnerships.\n\n"
                "## Key Priorities\n\n"
                "### 1. API Platform Expansion\n"
                "- Launch v2 REST API with improved rate limiting (PROJ-101, in progress)\n"
                "- Add GraphQL support for complex queries\n"
                "- Implement webhook system for real-time events (required by Acme Corp)\n"
                "- Set up Grafana monitoring dashboards (PROJ-105, blocked on PROJ-101)\n\n"
                "### 2. Developer Experience\n"
                "- New SDK for Python and TypeScript (PROJ-103 — docs pending)\n"
                "- Interactive API documentation\n"
                "- Developer portal with sandbox environment\n\n"
                "### 3. Strategic Partnerships\n"
                "- Acme Corp integration (high priority) — technical review next Tuesday, "
                "pilot kickoff week of the 24th.  See Technical Requirements on Confluence (doc-003).\n"
                "- TechFlow partnership evaluation\n"
                "- Open-source community engagement\n\n"
                "## Timeline\n"
                "- January: API v2 alpha, SDK development start\n"
                "- February: API v2 beta, Acme Corp integration kickoff\n"
                "- March: GA release, partnership reviews, board presentation (Thursday)\n\n"
                "## Success Metrics\n"
                "- API adoption: 50% increase in active API keys\n"
                "- Developer satisfaction: NPS > 40\n"
                "- Partnership revenue: 2 signed deals (Acme Corp + 1 TBD)\n"
            ),
            "last_modified": (now - timedelta(days=3)).isoformat(),
            "modified_by": "Kovács Péter",
            "word_count": 210,
        },
        "doc-003": {
            "document_id": "doc-003",
            "title": "Acme Corp Partnership — Technical Requirements",
            "source": "confluence",
            "content": (
                "# Acme Corp Partnership — Technical Requirements\n\n"
                "**Author:** Tóth László  |  **Last updated:** 2 days ago  |  "
                "**Status:** Under review\n\n"
                "## Overview\n"
                "This document outlines the technical requirements for the Acme Corp "
                "integration partnership, following the kickoff meeting (see Notion doc-005 "
                "for meeting notes).  John Smith (VP Engineering, Acme) is the technical lead "
                "on their side.\n\n"
                "## Integration Requirements\n\n"
                "### Authentication\n"
                "- OAuth 2.0 with PKCE flow (⚠️ fix PROJ-102 token refresh bug first)\n"
                "- API keys for server-to-server communication\n"
                "- Token refresh must be seamless — Acme's certification suite tests this\n\n"
                "### API Endpoints\n"
                "- REST API v2 endpoints (depends on PROJ-101 rate limiting completion)\n"
                "- Must support `RateLimit-*` headers per RFC 6585\n"
                "- GraphQL endpoint for complex data queries (future phase)\n\n"
                "### Webhooks\n"
                "- HMAC-SHA256 signed payloads\n"
                "- Exponential-backoff retries\n"
                "- Real-time event notifications for workflow triggers\n"
                "- Webhook integration PR: PROJ-104 (pending code review)\n\n"
                "### Monitoring\n"
                "- Grafana dashboards for partner API usage (PROJ-105, blocked on PROJ-101)\n"
                "- SLA: p99 latency < 500 ms, uptime > 99.9%\n"
                "- Current incident: p99 > 2 s spike — see #incidents on Slack\n\n"
                "## Timeline\n"
                "- Technical integration review: next Tuesday 10 AM CET (from John Smith's email)\n"
                "- Contract review: next Wednesday 3 PM CET\n"
                "- Pilot kickoff: week of the 24th\n\n"
                "## Contacts\n"
                "- John Smith — VP Engineering, Acme Corp\n"
                "- Sarah Chen — CEO, Acme Corp\n"
                "- Szabó Gábor — our DevOps lead for the integration\n"
                "- Varga Eszter — partnership manager\n"
            ),
            "last_modified": (now - timedelta(days=2)).isoformat(),
            "modified_by": "Tóth László",
            "word_count": 260,
        },
        "doc-005": {
            "document_id": "doc-005",
            "title": "Meeting Notes — Acme Corp Kickoff",
            "source": "notion",
            "content": (
                "# Meeting Notes — Acme Corp Kickoff\n\n"
                "**Date:** yesterday  |  **Author:** Varga Eszter  |  "
                "**Attendees:** Varga Eszter, Tóth László, John Smith (Acme), Sarah Chen (Acme)\n\n"
                "## Summary\n"
                "Productive kickoff meeting with Acme Corp.  Both teams aligned on the integration "
                "scope and timeline.  John Smith sent a follow-up email (mail-003) with confirmed "
                "next steps.\n\n"
                "## Key Decisions\n"
                "1. Technical integration review scheduled for next Tuesday 10 AM CET\n"
                "   - Our side: Szabó Gábor + API team\n"
                "   - Acme side: John Smith + Sarah Chen\n"
                "2. Contract review next Wednesday 3 PM CET\n"
                "3. Pilot kickoff targeting week of the 24th\n\n"
                "## Open Items\n"
                "- [ ] Fix auth token refresh bug (PROJ-102) — blocks Acme certification\n"
                "- [ ] Complete API rate limiting (PROJ-101) — Acme requires RFC 6585 headers\n"
                "- [ ] Review webhook integration PR (PROJ-104) — Acme needs this for pilot\n"
                "- [ ] Prepare demo for Thursday client review (evt-003)\n\n"
                "## Action Items\n"
                "| Owner | Action | Deadline |\n"
                "|-------|--------|----------|\n"
                "| Tóth László | Update Technical Requirements doc (doc-003) | Today |\n"
                "| Szabó Gábor | Prepare integration test environment | Next Monday |\n"
                "| Varga Eszter | Confirm review times with Acme via #acme-partnership | Today |\n"
                "| John Smith | Send Partnership Proposal v2 (attached to mail-003) | Done |\n"
            ),
            "last_modified": (now - timedelta(days=1)).isoformat(),
            "modified_by": "Varga Eszter",
            "word_count": 230,
        },
    }
    doc = mock_docs.get(document_id)
    if not doc:
        return {"status": "error", "message": f"Document not found: {document_id}"}
    return {"status": "success", "document": doc}


@mcp.tool()
def list_recent_documents(days: int = 7, source: str = "all") -> dict:
    """List recently modified documents.

    Args:
        days: Number of days to look back (default: 7)
        source: Filter by source platform (all, google_drive, notion, confluence)

    Returns:
        Dictionary with recently modified documents
    """
    now = _now()
    docs = [
        {
            "document_id": "doc-001",
            "title": "Q1 Platform Strategy",
            "source": "google_drive",
            "last_modified": (now - timedelta(days=3)).isoformat(),
            "modified_by": "Kovács Péter",
        },
        {
            "document_id": "doc-005",
            "title": "Meeting Notes - Acme Corp Kickoff",
            "source": "notion",
            "last_modified": (now - timedelta(days=1)).isoformat(),
            "modified_by": "Varga Eszter",
        },
        {
            "document_id": "doc-002",
            "title": "Sprint 23 Retrospective Notes",
            "source": "notion",
            "last_modified": (now - timedelta(days=5)).isoformat(),
            "modified_by": "Nagy Anna",
        },
        {
            "document_id": "doc-006",
            "title": "API v2 Design Document",
            "source": "confluence",
            "last_modified": (now - timedelta(days=2)).isoformat(),
            "modified_by": "Horváth Dávid",
        },
    ]

    if source != "all":
        docs = [d for d in docs if d["source"] == source]

    return {
        "status": "success",
        "period_days": days,
        "source_filter": source,
        "documents": docs,
        "total_count": len(docs),
    }


@mcp.tool()
def create_document(title: str, content: str, source: str = "google_drive", template: str = "") -> dict:
    """Create a new document.

    Args:
        title: Document title
        content: Document content (markdown format)
        source: Target platform (google_drive, notion, confluence)
        template: Optional template name (meeting_notes, project_brief, technical_spec)

    Returns:
        Dictionary with created document details
    """
    doc_id = f"doc-{datetime.now().strftime('%H%M%S')}"
    return {
        "status": "success",
        "message": "Document created successfully",
        "document": {
            "document_id": doc_id,
            "title": title,
            "source": source,
            "template_used": template or "none",
            "url": f"https://{source.replace('_', '.')}.com/d/{doc_id}",
            "created_at": _now().isoformat(),
        },
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
