"""MCP server for research_agent - web research tools with mock data."""

from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ResearchServer")


def _now() -> datetime:
    return datetime.now()


@mcp.tool()
def web_search(query: str, limit: int = 10) -> dict:
    """Search the web for information.

    Args:
        query: Search query
        limit: Maximum number of results

    Returns:
        Dictionary with search results
    """
    # Mock: return results that look realistic for common query patterns
    results = [
        {
            "title": f"Understanding {query} - A Comprehensive Guide",
            "url": f"https://example.com/guide/{query.replace(' ', '-').lower()}",
            "snippet": f"A detailed overview of {query}, covering key concepts, best practices, and recent developments in the field...",
            "source": "example.com",
            "date": (_now() - timedelta(days=5)).strftime("%Y-%m-%d"),
        },
        {
            "title": f"{query}: Latest News and Updates",
            "url": f"https://news.example.com/{query.replace(' ', '-').lower()}",
            "snippet": f"Stay up to date with the latest developments in {query}. Recent announcements include new features and industry partnerships...",
            "source": "news.example.com",
            "date": (_now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        },
        {
            "title": f"Best Practices for {query} in 2026",
            "url": f"https://blog.example.com/best-practices-{query.replace(' ', '-').lower()}-2026",
            "snippet": f"Learn the top strategies and best practices for {query} this year. Industry experts share their insights...",
            "source": "blog.example.com",
            "date": (_now() - timedelta(days=14)).strftime("%Y-%m-%d"),
        },
    ]

    return {
        "status": "success",
        "query": query,
        "results": results[:limit],
        "result_count": len(results),
    }


@mcp.tool()
def fetch_webpage(url: str) -> dict:
    """Fetch and extract content from a webpage.

    Args:
        url: The URL to fetch

    Returns:
        Dictionary with extracted page content
    """
    return {
        "status": "success",
        "url": url,
        "title": "Extracted Page Title",
        "content": (
            "# Page Content\n\n"
            "This is the extracted main content from the webpage. "
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
                "and infrastructure teams. Previously, he was a Senior Director at TechFlow Inc. "
                "He has 15+ years of experience in distributed systems and API platforms."
            ),
            "recent_activity": [
                "Spoke at API World 2025 on 'Scaling APIs to 1M+ requests/second'",
                "Published article on microservices architecture in InfoQ",
                "Acme Corp announced Series C funding ($50M) in January 2026",
            ],
            "mutual_connections": ["Tóth László", "Varga Eszter"],
        },
        "kovács péter": {
            "name": "Kovács Péter",
            "title": "Tech Lead",
            "company": "Our Company",
            "location": "Budapest, Hungary",
            "linkedin": "https://linkedin.com/in/kovacspeeter",
            "background": (
                "Kovács Péter is a Tech Lead focusing on API platform development. "
                "He has been with the company for 4 years and leads the backend team."
            ),
            "recent_activity": [
                "Leading API v2 development initiative",
                "Mentoring junior developers on the team",
            ],
            "mutual_connections": ["Nagy Anna", "Szabó Gábor", "Horváth Dávid"],
        },
    }

    profile = mock_profiles.get(name.lower())
    if not profile:
        # Generate a generic profile for unknown names
        profile = {
            "name": name,
            "title": "Professional",
            "company": company or "Unknown",
            "location": "Not available",
            "background": f"Limited information available for {name}. Consider reaching out directly for more details.",
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
                "Acme Corp is an enterprise software company specializing in workflow automation "
                "and integration platforms. They serve Fortune 500 companies and have a strong "
                "presence in the financial services and healthcare sectors."
            ),
            "recent_news": [
                {
                    "title": "Acme Corp Raises $50M Series C",
                    "date": "2026-01-15",
                    "summary": "Funding led by Sequoia Capital to expand enterprise platform capabilities.",
                },
                {
                    "title": "Acme Corp Launches New API Platform",
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
                f"{'topic: ' + topic if topic else 'general discussion'}. "
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
