"""MCP Server: Lead Generation & Qualification

Integrates with:
- Apollo.io: Company search & lead qualification (free plan: organizations only)

Tools:
- search_companies: Search for companies matching criteria
- qualify_lead: Score a lead using Apollo company data
- find_contacts: Find decision-makers (requires paid Apollo plan or Hunter)
"""

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types
from typing import Any
import httpx
import os

APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "vp42h07NcldZU1xA1769TA")

server = Server("lead-gen")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_companies",
            description="Search for companies by industry, size, location via Apollo.io",
            inputSchema={
                "type": "object",
                "properties": {
                    "industry": {"type": "string", "description": "Target industry (e.g. cybersecurity, SaaS, fintech)"},
                    "min_employees": {"type": "integer", "description": "Minimum company size"},
                    "max_employees": {"type": "integer", "description": "Maximum company size"},
                    "location": {"type": "string", "description": "City, state, or country"},
                    "keywords": {"type": "string", "description": "Keywords for company description/tags"},
                    "limit": {"type": "integer", "description": "Max results (max 25)"},
                },
                "required": [],
            },
        ),
        types.Tool(
            name="qualify_lead",
            description="Score and qualify a lead using Apollo company data",
            inputSchema={
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "Company name"},
                    "domain": {"type": "string", "description": "Company domain (preferred)"},
                },
                "required": ["company"],
            },
        ),
        types.Tool(
            name="find_contacts",
            description="List known contacts at a company (uses Apollo — may need paid plan)",
            inputSchema={
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "Company name"},
                    "domain": {"type": "string", "description": "Company domain"},
                    "role": {"type": "string", "description": "Target role title (e.g. CTO, VP Sales)"},
                },
                "required": ["company"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name == "search_companies":
        result = await _search_companies(arguments)
        return [types.TextContent(type="text", text=result)]
    elif name == "qualify_lead":
        result = await _qualify_lead(arguments)
        return [types.TextContent(type="text", text=result)]
    elif name == "find_contacts":
        result = await _find_contacts(arguments)
        return [types.TextContent(type="text", text=result)]
    raise ValueError(f"Unknown tool: {name}")


async def _apollo_api(method: str, endpoint: str, payload: dict) -> dict | None:
    """Helper to call Apollo.io API."""
    url = f"https://api.apollo.io/v1/{endpoint}"
    headers = {"Content-Type": "application/json", "x-api-key": APOLLO_API_KEY}
    async with httpx.AsyncClient(timeout=20) as client:
        if method == "POST":
            resp = await client.post(url, json=payload, headers=headers)
        else:
            resp = await client.get(url, params=payload, headers=headers)
        if resp.status_code != 200:
            return None
        return resp.json()


async def _search_companies(args: dict) -> str:
    payload: dict[str, Any] = {"page": 1, "per_page": min(args.get("limit", 10), 25)}
    if ind := args.get("industry"):
        payload["q_organization_industry_tags"] = [ind]
    if kw := args.get("keywords"):
        payload["q_keywords"] = kw
    if loc := args.get("location"):
        payload["q_organization_location"] = loc
    min_e, max_e = args.get("min_employees"), args.get("max_employees")
    if min_e or max_e:
        r: dict[str, int] = {}
        if min_e: r["min"] = min_e
        if max_e: r["max"] = max_e
        payload["organization_num_employees_ranges"] = [str(r)]

    data = await _apollo_api("POST", "mixed_companies/search", payload)
    if not data:
        return "Apollo API error — check your plan and API key."

    orgs = data.get("organizations", [])
    if not orgs:
        return "No companies found matching those criteria."

    lines = [f"Found {data.get('total_entries', len(orgs))} companies (top {len(orgs)}):\n"]
    for org in orgs[:10]:
        lines.append(
            f"• {org.get('name', '?')}  ({org.get('primary_domain', 'no domain')})\n"
            f"  {org.get('short_description', '')[:120]}\n"
            f"  👥 {org.get('estimated_num_employees', '?')}  "
            f"🏷️ {', '.join(org.get('industry_tags', [])[:3]) if org.get('industry_tags') else '?'}\n"
        )
    return "\n".join(lines)


async def _qualify_lead(args: dict) -> str:
    company = args.get("company", "")
    domain = args.get("domain", "")

    # Resolve domain if not provided
    if not domain:
        data = await _apollo_api("POST", "organizations/search", {"q_organization_name": company, "per_page": 1})
        if data and data.get("organizations"):
            domain = data["organizations"][0].get("primary_domain", "")

    if not domain:
        return f"Could not find domain for {company}."

    data = await _apollo_api("POST", "organizations/search", {"q_organization_domains": [domain], "per_page": 1})
    if not data or not data.get("organizations"):
        return f"No data found for {company} ({domain})"

    org = data["organizations"][0]

    # Scoring
    score = 10
    reasons = ["Base score: 10"]

    emp = org.get("estimated_num_employees", 0) or 0
    if emp >= 200:
        score += 25; reasons.append(f"+25: Enterprise ({emp} employees)")
    elif emp >= 50:
        score += 15; reasons.append(f"+15: Mid-market ({emp} employees)")
    elif emp >= 10:
        score += 10; reasons.append(f"+10: SMB ({emp} employees)")

    rev = org.get("estimated_revenue", {})
    if isinstance(rev, dict) and rev.get("value"):
        score += 15; reasons.append(f"+15: Revenue ${rev['value']:,.0f}")

    industry_tags = org.get("industry_tags", [])
    industry_text = str(industry_tags).lower()
    if any(w in industry_text for w in ["software", "information technology", "saas", "cyber"]):
        score += 10; reasons.append("+10: Tech/SaaS industry")

    if org.get("linkedin_url"):
        score += 5; reasons.append("+5: Active LinkedIn presence")

    tech = org.get("technology_names", []) or []
    if tech:
        score += 10; reasons.append(f"+10: {len(tech)} technologies in stack")

    keywords = org.get("keywords", []) or []
    channel_kw = [k for k in keywords if any(
        w in k.lower() for w in ["partn", "channel", "reseller", "distribut", "alliance", "revenue", "growth"])]
    if channel_kw:
        score += 10; reasons.append(f"+10: Channel/growth keywords found")

    if org.get("funding_events"):
        score += 10; reasons.append(f"+10: Venture-backed")

    score = min(score, 100)
    tier = "🔥 HOT" if score >= 75 else "✅ WARM" if score >= 50 else "🟡 COOL"

    return (
        f"Lead: {org.get('name', company)} ({domain})\n"
        f"Score: {score}/100 — {tier}\n"
        f"\nBreakdown:\n" + "\n".join(reasons) + "\n\n"
        f"Profile: {emp} employees | "
        f"{', '.join(industry_tags[:3]) if industry_tags else '?'}\n"
        f"Tech: {', '.join(tech[:5]) if tech else '?'}"
    )


async def _find_contacts(args: dict) -> str:
    """Note: Apollo people search requires a paid plan. This is a stub."""
    company = args.get("company", "")
    domain = args.get("domain", "")
    role = args.get("role", "")

    # Try to resolve domain
    if not domain:
        data = await _apollo_api("POST", "organizations/search", {"q_organization_name": company, "per_page": 1})
        if data and data.get("organizations"):
            domain = data["organizations"][0].get("primary_domain", "")

    return (
        f"Contact search at {company} ({domain or 'domain unknown'})\n\n"
        f"⚠️  Apollo people search requires a paid plan.\n"
        f"To find contacts, upgrade your Apollo account or use:\n"
        f"• LinkedIn Sales Navigator\n"
        f"• Hunter.io (email finder)\n"
        f"• Lusha / ZoomInfo\n\n"
        f"Looking for: {role if role else 'decision-makers'}"
    )


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, InitializationOptions(
            server_name="lead-gen", server_version="0.1.0",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            ),
        ))


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())