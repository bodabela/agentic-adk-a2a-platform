"""MCP server for research_agent - web research tools with mock data."""

from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ResearchServer")


def _now() -> datetime:
    return datetime.now()


# ---------------------------------------------------------------------------
# Themed search results keyed by topic keywords.  When a query matches one of
# these keywords the corresponding results are returned, giving the illusion
# that the assistant's research is informed by emails, calendar entries and
# task-board items that live in the other agents.
# ---------------------------------------------------------------------------

_THEMED_RESULTS: dict[str, list[dict]] = {
    "rate limit": [
        {
            "title": "API Rate Limiting Best Practices — IETF RFC 6585 & Beyond",
            "url": "https://apiguide.io/rate-limiting-best-practices",
            "snippet": (
                "Implement token-bucket or sliding-window counters and return "
                "standardised RateLimit-* headers (RFC 6585).  Major providers "
                "like Stripe and GitHub use 429 responses with Retry-After…"
            ),
            "source": "apiguide.io",
        },
        {
            "title": "How Acme Corp Scaled Their API to 1M req/s — John Smith at API World 2025",
            "url": "https://apiworld.dev/talks/acme-scaling-api",
            "snippet": (
                "John Smith, VP Engineering at Acme Corp, shares how their "
                "platform team introduced adaptive rate limiting and achieved "
                "sub-10 ms p99 latency at scale…"
            ),
            "source": "apiworld.dev",
        },
        {
            "title": "Configurable Rate Limiting with Redis — A Step-by-Step Tutorial",
            "url": "https://blog.techflow.io/redis-rate-limiting-tutorial",
            "snippet": (
                "Use Redis sorted sets for sliding-window rate limiting.  This "
                "guide walks through a production-grade implementation with "
                "per-client and per-endpoint limits…"
            ),
            "source": "blog.techflow.io",
        },
    ],
    "token refresh": [
        {
            "title": "OAuth 2.0 Token Refresh — Avoiding Intermittent 401 Errors",
            "url": "https://auth0.com/blog/token-refresh-best-practices",
            "snippet": (
                "Long-lived sessions often trigger 401 errors when the access "
                "token expires mid-request.  Use proactive refresh with a TTL "
                "buffer and a retry-with-refresh interceptor…"
            ),
            "source": "auth0.com",
        },
        {
            "title": "Debugging Intermittent Auth Failures in Microservices",
            "url": "https://devops.stackexchange.com/q/token-refresh-race-condition",
            "snippet": (
                "A common root cause is a race condition where multiple threads "
                "try to refresh the same token concurrently.  Lock-free "
                "single-flight patterns solve this…"
            ),
            "source": "devops.stackexchange.com",
        },
        {
            "title": "RFC 6749 §6 — Refreshing an Access Token",
            "url": "https://datatracker.ietf.org/doc/html/rfc6749#section-6",
            "snippet": (
                "The authorization server issues a new access token (and "
                "optionally a new refresh token) in response to a valid "
                "refresh-token grant…"
            ),
            "source": "ietf.org",
        },
    ],
    "acme corp": [
        {
            "title": "Acme Corp Raises $50M Series C to Expand Enterprise Platform",
            "url": "https://techcrunch.com/2026/01/15/acme-corp-series-c",
            "snippet": (
                "Enterprise software company Acme Corp closed a $50 M Series C "
                "led by Sequoia Capital.  CEO Sarah Chen says the funds will "
                "accelerate API platform and partnership capabilities…"
            ),
            "source": "techcrunch.com",
        },
        {
            "title": "Acme Corp Launches New Integration Platform — 200+ Connectors",
            "url": "https://acmecorp.com/blog/integration-platform-launch",
            "snippet": (
                "Acme Corp's new platform enables seamless integration with "
                "200+ enterprise applications via REST, GraphQL and webhook "
                "connectors.  Aimed at Fortune 500 workflow automation…"
            ),
            "source": "acmecorp.com",
        },
        {
            "title": "Acme Corp Partnership Program — Technical Requirements & Onboarding",
            "url": "https://partners.acmecorp.com/technical-requirements",
            "snippet": (
                "Partners must support OAuth 2.0, provide webhook endpoints "
                "for real-time events, and pass the integration certification "
                "suite before going live…"
            ),
            "source": "partners.acmecorp.com",
        },
    ],
    "api latency": [
        {
            "title": "Diagnosing API Latency Spikes — Connection Pool Exhaustion",
            "url": "https://engineering.medium.com/api-latency-connection-pool",
            "snippet": (
                "When p99 latency suddenly exceeds 2 s, the most common culprit "
                "is database connection pool exhaustion.  Monitor active vs idle "
                "connections and scale the pool before saturation…"
            ),
            "source": "engineering.medium.com",
        },
        {
            "title": "Production Incident Playbook — Latency Spike Response",
            "url": "https://sre.google/playbook/latency-spikes",
            "snippet": (
                "Step 1: Check upstream dependencies.  Step 2: Verify connection "
                "pool metrics.  Step 3: Look for recent deployments that changed "
                "query patterns or pool configuration…"
            ),
            "source": "sre.google",
        },
        {
            "title": "Grafana Dashboard Templates for API Monitoring",
            "url": "https://grafana.com/grafana/dashboards/api-monitoring",
            "snippet": (
                "Pre-built dashboards for API latency (p50/p95/p99), error "
                "rates, and throughput.  Ideal for post-incident review and "
                "ongoing SLO tracking…"
            ),
            "source": "grafana.com",
        },
    ],
    "webhook": [
        {
            "title": "Designing Reliable Webhook Systems — Retry, Idempotency & Signing",
            "url": "https://hookdeck.com/guides/reliable-webhooks",
            "snippet": (
                "Ensure at-least-once delivery with exponential backoff retries, "
                "idempotency keys, and HMAC-SHA256 payload signing.  Partners "
                "like Acme Corp require signed payloads…"
            ),
            "source": "hookdeck.com",
        },
        {
            "title": "Webhook Integration Patterns for Enterprise APIs",
            "url": "https://blog.postman.com/webhook-integration-patterns",
            "snippet": (
                "Compare push (webhook) vs pull (polling) models.  When to use "
                "fan-out, how to handle back-pressure, and real-world examples "
                "from Stripe, GitHub and Acme Corp…"
            ),
            "source": "blog.postman.com",
        },
    ],
    "sprint retrospective": [
        {
            "title": "Running Effective Sprint Retrospectives — A Facilitator's Guide",
            "url": "https://www.atlassian.com/team-playbook/plays/retrospective",
            "snippet": (
                "Use the 'What went well / What to improve / Action items' "
                "format.  Timebox to 60 minutes and assign owners to every "
                "action item…"
            ),
            "source": "atlassian.com",
        },
        {
            "title": "Sprint Velocity Trends — When Below Average Is a Signal",
            "url": "https://agile.stackexchange.com/q/velocity-trend-analysis",
            "snippet": (
                "A velocity dip for one sprint is normal.  Two consecutive "
                "sprints below the 3-sprint average suggests systemic blockers — "
                "check for scope creep or dependency bottlenecks…"
            ),
            "source": "agile.stackexchange.com",
        },
    ],
}


@mcp.tool()
def web_search(query: str, limit: int = 10) -> dict:
    """Search the web for information.

    Args:
        query: Search query
        limit: Maximum number of results

    Returns:
        Dictionary with search results
    """
    now = _now()
    query_lower = query.lower()

    # Try to match themed results first
    for keyword, themed in _THEMED_RESULTS.items():
        if keyword in query_lower:
            results = []
            for i, r in enumerate(themed):
                results.append({
                    **r,
                    "date": (now - timedelta(days=(i * 3 + 1))).strftime("%Y-%m-%d"),
                })
            return {
                "status": "success",
                "query": query,
                "results": results[:limit],
                "result_count": len(results),
            }

    # Fallback: generic but still project-flavoured results
    results = [
        {
            "title": f"Understanding {query} — A Comprehensive Guide",
            "url": f"https://example.com/guide/{query.replace(' ', '-').lower()}",
            "snippet": f"A detailed overview of {query}, covering key concepts, best practices, and recent developments in the field…",
            "source": "example.com",
            "date": (now - timedelta(days=5)).strftime("%Y-%m-%d"),
        },
        {
            "title": f"{query}: Latest News and Updates (2026)",
            "url": f"https://news.example.com/{query.replace(' ', '-').lower()}",
            "snippet": f"Stay up to date with the latest developments in {query}.  Recent announcements include new features and industry partnerships…",
            "source": "news.example.com",
            "date": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
        },
        {
            "title": f"Best Practices for {query} in 2026",
            "url": f"https://blog.example.com/best-practices-{query.replace(' ', '-').lower()}-2026",
            "snippet": f"Learn the top strategies and best practices for {query} this year.  Industry experts share their insights…",
            "source": "blog.example.com",
            "date": (now - timedelta(days=14)).strftime("%Y-%m-%d"),
        },
    ]

    return {
        "status": "success",
        "query": query,
        "results": results[:limit],
        "result_count": len(results),
    }


# ---------------------------------------------------------------------------
# Themed page content keyed by URL substring.
# ---------------------------------------------------------------------------

_THEMED_PAGES: dict[str, dict] = {
    "acmecorp.com": {
        "title": "Acme Corp — Enterprise Integration Platform",
        "content": (
            "# Acme Corp Integration Platform\n\n"
            "## Overview\n"
            "Acme Corp provides a workflow automation and integration platform serving "
            "Fortune 500 companies in financial services and healthcare.\n\n"
            "## Partnership Technical Requirements\n"
            "- **Authentication**: OAuth 2.0 with PKCE flow\n"
            "- **API Format**: REST (OpenAPI 3.1) and GraphQL\n"
            "- **Webhooks**: HMAC-SHA256 signed payloads, exponential-backoff retries\n"
            "- **Rate Limits**: Partners must respect `RateLimit-*` headers (RFC 6585)\n"
            "- **Certification**: Pass the integration test suite before production access\n\n"
            "## Key Contacts\n"
            "- Sarah Chen — CEO\n"
            "- John Smith — VP of Engineering (technical integration lead)\n"
            "- Maria Garcia — CTO\n\n"
            "## Recent News\n"
            "- Series C funding: $50 M led by Sequoia Capital (January 2026)\n"
            "- New platform launch: 200+ enterprise connectors (November 2025)\n"
        ),
        "word_count": 142,
    },
    "rate-limit": {
        "title": "API Rate Limiting Best Practices — RFC 6585 & Beyond",
        "content": (
            "# API Rate Limiting Best Practices\n\n"
            "## Why Rate Limiting Matters\n"
            "Rate limiting protects your API from abuse and ensures fair resource "
            "allocation across clients.\n\n"
            "## Recommended Algorithms\n"
            "1. **Token Bucket** — smooth bursts, simple to implement with Redis\n"
            "2. **Sliding Window** — more accurate than fixed windows, moderate complexity\n"
            "3. **Leaky Bucket** — constant output rate, good for queue-based systems\n\n"
            "## Standard Headers (RFC 6585)\n"
            "- `RateLimit-Limit`: maximum requests per window\n"
            "- `RateLimit-Remaining`: requests left in current window\n"
            "- `RateLimit-Reset`: seconds until the window resets\n"
            "- Return `429 Too Many Requests` with a `Retry-After` header\n\n"
            "## Per-Client vs Per-Endpoint\n"
            "Configure limits at both levels.  Enterprise partners like Acme Corp "
            "typically need higher per-client limits with per-endpoint overrides.\n"
        ),
        "word_count": 138,
    },
    "token-refresh": {
        "title": "OAuth 2.0 Token Refresh — Avoiding Intermittent 401 Errors",
        "content": (
            "# Fixing Intermittent 401 Errors During Token Refresh\n\n"
            "## The Problem\n"
            "Users report random 401 errors during long sessions.  The root cause is "
            "almost always a race condition between the token expiry check and the "
            "refresh request.\n\n"
            "## Solution: Proactive Refresh with Single-Flight Pattern\n"
            "1. Refresh the token **before** it expires (e.g. when 80 % of TTL has passed)\n"
            "2. Use a single-flight lock so only one thread refreshes at a time\n"
            "3. Queue other requests and replay them once the new token is available\n\n"
            "## Implementation Checklist\n"
            "- [ ] Add TTL-buffer check to the auth interceptor\n"
            "- [ ] Implement single-flight refresh lock\n"
            "- [ ] Add retry-with-new-token for in-flight 401 responses\n"
            "- [ ] Write integration tests with clock-mocking\n\n"
            "## Related\n"
            "- RFC 6749 §6 — Refreshing an Access Token\n"
            "- See also: database connection pool exhaustion as a secondary cause of "
            "intermittent failures\n"
        ),
        "word_count": 155,
    },
    "latency": {
        "title": "Diagnosing API Latency Spikes — Connection Pool Exhaustion",
        "content": (
            "# Diagnosing API Latency Spikes\n\n"
            "## Symptom\n"
            "p99 latency exceeds 2 s; Grafana dashboard shows sudden spike.\n\n"
            "## Most Common Root Cause: Connection Pool Exhaustion\n"
            "When all database connections are in use, new requests queue up waiting "
            "for a free connection, causing latency to skyrocket.\n\n"
            "## Diagnostic Steps\n"
            "1. Check `active_connections` vs `pool_size` in your DB metrics\n"
            "2. Look for long-running queries or uncommitted transactions\n"
            "3. Correlate with recent deployments (connection pool config changes)\n"
            "4. Verify connection leak detection is enabled\n\n"
            "## Immediate Mitigation\n"
            "- Scale up `max_pool_size` (temporary relief)\n"
            "- Kill long-running queries\n"
            "- Enable connection timeout to prevent leaks\n\n"
            "## Post-Incident\n"
            "- Schedule a post-incident review\n"
            "- Add Grafana alerts for pool utilisation > 80 %\n"
            "- See task: 'Set up monitoring dashboards for v2 API'\n"
        ),
        "word_count": 148,
    },
    "grafana": {
        "title": "Grafana Dashboard Templates for API Monitoring",
        "content": (
            "# Grafana API Monitoring Dashboards\n\n"
            "## Recommended Panels\n"
            "- **Latency**: p50, p95, p99 over time (line chart)\n"
            "- **Error Rate**: 4xx vs 5xx per endpoint (stacked bar)\n"
            "- **Throughput**: requests/second by endpoint (line chart)\n"
            "- **Connection Pool**: active vs idle connections (gauge + time series)\n"
            "- **Rate Limiting**: 429 responses per client (heatmap)\n\n"
            "## Alerting Rules\n"
            "- p99 latency > 2 s for 5 minutes → PagerDuty critical\n"
            "- Error rate > 5 % for 10 minutes → Slack #incidents\n"
            "- Connection pool utilisation > 80 % → Slack #platform-dev\n\n"
            "## Integration\n"
            "Import dashboard JSON into your Grafana instance.  Works with "
            "Prometheus, InfluxDB, and CloudWatch data sources.\n"
        ),
        "word_count": 118,
    },
}


@mcp.tool()
def fetch_webpage(url: str) -> dict:
    """Fetch and extract content from a webpage.

    Args:
        url: The URL to fetch

    Returns:
        Dictionary with extracted page content
    """
    url_lower = url.lower()

    # Try to match themed page content
    for keyword, page in _THEMED_PAGES.items():
        if keyword in url_lower:
            return {
                "status": "success",
                "url": url,
                "title": page["title"],
                "content": page["content"],
                "word_count": page["word_count"],
                "fetched_at": _now().isoformat(),
            }

    # Fallback generic
    return {
        "status": "success",
        "url": url,
        "title": "Extracted Page Title",
        "content": (
            "# Page Content\n\n"
            "This is the extracted main content from the webpage.  "
            "In a real implementation, this would contain the actual page text "
            "with HTML stripped and content cleaned up for readability.\n\n"
            "## Key Points\n"
            "- Point 1: Important information extracted from the page\n"
            "- Point 2: Additional relevant details\n"
            "- Point 3: Supporting context and data\n\n"
            "## Summary\n"
            "The page discusses relevant topics with actionable insights."
        ),
        "word_count": 85,
        "fetched_at": _now().isoformat(),
    }


@mcp.tool()
def lookup_person(name: str, company: str = "") -> dict:
    """Look up professional information about a person.

    Args:
        name: Person's name to look up
        company: Optional company name to narrow the search

    Returns:
        Dictionary with person's professional profile
    """
    mock_profiles = {
        "john smith": {
            "name": "John Smith",
            "title": "VP of Engineering",
            "company": "Acme Corp",
            "location": "San Francisco, CA",
            "linkedin": "https://linkedin.com/in/johnsmith",
            "background": (
                "John Smith is VP of Engineering at Acme Corp, where he leads the platform "
                "and infrastructure teams.  Previously, he was a Senior Director at TechFlow Inc.  "
                "He has 15+ years of experience in distributed systems and API platforms."
            ),
            "recent_activity": [
                "Spoke at API World 2025 on 'Scaling APIs to 1M+ requests/second'",
                "Published article on microservices architecture in InfoQ",
                "Acme Corp announced Series C funding ($50 M) in January 2026",
            ],
            "mutual_connections": ["Tóth László", "Varga Eszter"],
        },
        "sarah chen": {
            "name": "Sarah Chen",
            "title": "CEO",
            "company": "Acme Corp",
            "location": "San Francisco, CA",
            "linkedin": "https://linkedin.com/in/sarahchen",
            "background": (
                "Sarah Chen is the CEO and co-founder of Acme Corp.  Under her leadership "
                "the company grew from 50 to 800+ employees and closed a $50 M Series C.  "
                "Previously at McKinsey and Google Cloud."
            ),
            "recent_activity": [
                "Led Acme Corp's $50 M Series C (Sequoia Capital, Jan 2026)",
                "Keynote at SaaStr Annual 2025 on enterprise platform strategy",
            ],
            "mutual_connections": ["Tóth László"],
        },
        "kovács péter": {
            "name": "Kovács Péter",
            "title": "Tech Lead",
            "company": "Our Company",
            "location": "Budapest, Hungary",
            "linkedin": "https://linkedin.com/in/kovacspeeter",
            "background": (
                "Kovács Péter is a Tech Lead focusing on API platform development.  "
                "He has been with the company for 4 years and leads the backend team.  "
                "Currently investigating a production latency incident related to DB "
                "connection pool exhaustion."
            ),
            "recent_activity": [
                "Leading API v2 development initiative (Sprint 24)",
                "Investigating production latency spike (p99 > 2 s) — connection pool issue",
                "Mentoring junior developers on the team",
            ],
            "mutual_connections": ["Nagy Anna", "Szabó Gábor", "Horváth Dávid"],
        },
        "nagy anna": {
            "name": "Nagy Anna",
            "title": "Engineering Manager",
            "company": "Our Company",
            "location": "Budapest, Hungary",
            "linkedin": "https://linkedin.com/in/nagyanna",
            "background": (
                "Nagy Anna is an Engineering Manager overseeing sprint planning and "
                "delivery for the Platform team.  She organises Sprint 24 planning "
                "and coordinates the Acme Corp partnership workstream."
            ),
            "recent_activity": [
                "Finalising Sprint 24 planning agenda (feature requests + tech debt)",
                "Coordinating Q1 deliverables review for the board presentation",
            ],
            "mutual_connections": ["Kovács Péter", "Szabó Gábor", "Tóth László"],
        },
        "tóth lászló": {
            "name": "Tóth László",
            "title": "Head of Product",
            "company": "Our Company",
            "location": "Budapest, Hungary",
            "linkedin": "https://linkedin.com/in/tothlaszlo",
            "background": (
                "Tóth László is Head of Product, responsible for Q1 deliverables, "
                "the board presentation, and the Acme Corp technical requirements document.  "
                "He works closely with the engineering and partnerships teams."
            ),
            "recent_activity": [
                "Preparing Q1 deliverables report for the board (due Wednesday)",
                "Authored Acme Corp Partnership — Technical Requirements (Confluence)",
            ],
            "mutual_connections": ["Nagy Anna", "Varga Eszter", "John Smith"],
        },
        "horváth dávid": {
            "name": "Horváth Dávid",
            "title": "Senior Backend Engineer",
            "company": "Our Company",
            "location": "Budapest, Hungary",
            "linkedin": "https://linkedin.com/in/horvathdavid",
            "background": (
                "Horváth Dávid is a Senior Backend Engineer working on API v2 "
                "infrastructure.  He completed the v2 staging deployment and is "
                "responsible for the monitoring dashboards (PROJ-105, currently blocked)."
            ),
            "recent_activity": [
                "Completed API v2 staging deployment",
                "Authored API v2 Design Document (Confluence)",
                "Waiting on PROJ-101 (rate limiting) to unblock PROJ-105 (dashboards)",
            ],
            "mutual_connections": ["Kovács Péter", "Szabó Gábor", "Kiss Márta"],
        },
        "szabó gábor": {
            "name": "Szabó Gábor",
            "title": "DevOps Engineer",
            "company": "Our Company",
            "location": "Budapest, Hungary",
            "linkedin": "https://linkedin.com/in/szabogabor",
            "background": (
                "Szabó Gábor is the team's DevOps engineer.  He maintains the CI/CD "
                "pipeline, fixed a flaky test issue this sprint, and will attend the "
                "Acme Corp technical integration review."
            ),
            "recent_activity": [
                "Fixed flaky test in main branch CI pipeline",
                "Invited to Acme Corp technical integration review (next Tuesday)",
            ],
            "mutual_connections": ["Kovács Péter", "Horváth Dávid", "Nagy Anna"],
        },
        "varga eszter": {
            "name": "Varga Eszter",
            "title": "Partnership Manager",
            "company": "Our Company",
            "location": "Budapest, Hungary",
            "linkedin": "https://linkedin.com/in/vargaeszter",
            "background": (
                "Varga Eszter manages strategic partnerships.  She is the main point "
                "of contact for the Acme Corp partnership and wrote the kickoff "
                "meeting notes."
            ),
            "recent_activity": [
                "Confirmed Acme Corp technical review for Thursday with John Smith",
                "Authored 'Meeting Notes — Acme Corp Kickoff' (Notion)",
            ],
            "mutual_connections": ["Tóth László", "John Smith", "Sarah Chen"],
        },
    }

    profile = mock_profiles.get(name.lower())
    if not profile:
        profile = {
            "name": name,
            "title": "Professional",
            "company": company or "Unknown",
            "location": "Not available",
            "background": f"Limited information available for {name}.  Consider reaching out directly for more details.",
            "recent_activity": [],
            "mutual_connections": [],
        }

    return {"status": "success", "person": profile}


@mcp.tool()
def lookup_company(name: str) -> dict:
    """Look up information about a company.

    Args:
        name: Company name to look up

    Returns:
        Dictionary with company information
    """
    mock_companies = {
        "acme corp": {
            "name": "Acme Corp",
            "industry": "Enterprise Software",
            "size": "500-1000 employees",
            "founded": 2015,
            "headquarters": "San Francisco, CA",
            "description": (
                "Acme Corp is an enterprise software company specialising in workflow automation "
                "and integration platforms.  They serve Fortune 500 companies and have a strong "
                "presence in the financial services and healthcare sectors.  Currently in active "
                "partnership discussions with our company — technical integration review scheduled "
                "for next Tuesday."
            ),
            "recent_news": [
                {
                    "title": "Acme Corp Raises $50M Series C",
                    "date": "2026-01-15",
                    "summary": "Funding led by Sequoia Capital to expand enterprise platform capabilities.",
                },
                {
                    "title": "Acme Corp Launches New API Platform — 200+ Connectors",
                    "date": "2025-11-20",
                    "summary": "New platform enables seamless integration with 200+ enterprise applications.",
                },
            ],
            "key_people": [
                {"name": "Sarah Chen", "title": "CEO"},
                {"name": "John Smith", "title": "VP of Engineering"},
                {"name": "Maria Garcia", "title": "CTO"},
            ],
            "website": "https://acmecorp.com",
        },
    }

    company = mock_companies.get(name.lower())
    if not company:
        company = {
            "name": name,
            "industry": "Unknown",
            "size": "Unknown",
            "description": f"Limited information available for {name}.",
            "recent_news": [],
            "key_people": [],
        }

    return {"status": "success", "company": company}


@mcp.tool()
def prepare_meeting_brief(attendees: str, topic: str = "") -> dict:
    """Compile a meeting preparation brief for attendees and topics.

    Args:
        attendees: Comma-separated list of attendee names
        topic: Meeting topic or agenda (optional)

    Returns:
        Dictionary with meeting preparation brief
    """
    attendee_list = [a.strip() for a in attendees.split(",") if a.strip()]

    briefs = []
    for attendee in attendee_list:
        lookup = lookup_person(attendee)
        if lookup["status"] == "success":
            person = lookup["person"]
            briefs.append({
                "name": person["name"],
                "title": person.get("title", "Unknown"),
                "company": person.get("company", "Unknown"),
                "key_points": person.get("recent_activity", [])[:2],
                "talking_points": [
                    f"Ask about {person.get('recent_activity', ['their recent work'])[0]}"
                ] if person.get("recent_activity") else [],
            })

    return {
        "status": "success",
        "meeting_brief": {
            "topic": topic or "General meeting",
            "attendees": briefs,
            "preparation_notes": (
                f"Meeting with {len(attendee_list)} attendee(s) on "
                f"{'topic: ' + topic if topic else 'general discussion'}.  "
                "Review the attendee profiles above for context and talking points."
            ),
            "suggested_agenda": [
                "Introductions and context setting (5 min)",
                f"{'Discussion: ' + topic if topic else 'Main discussion'} (20 min)",
                "Action items and next steps (5 min)",
            ],
        },
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
