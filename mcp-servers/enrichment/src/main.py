"""MCP Server: Data Enrichment

Integrates with:
- Apollo.io: Company enrichment (free plan: organizations only)

Tools:
- enrich_company: Get company profile, size, tech stack, funding
- enrich_contact: Note — requires paid Apollo or alternative service
- verify_email: Note — Hunter.io account is restricted
"""

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types
from typing import Any
import httpx
import os

APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "vp42h07NcldZU1xA1769TA")

server = Server("enrichment")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="enrich_company",
            description="Enrich company profile via Apollo.io: employees, revenue, tech stack, industry",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Company domain"},
                    "company": {"type": "string", "description": "Company name (fallback)"},
                },
                "required": [],
            },
        ),
        types.Tool(
            name="enrich_contact",
            description="Find contact email/social — requires upgraded Apollo or Hunter",
            inputSchema={
                "type": "object",
                "properties": {
                    "first_name": {"type": "string"},
                    "last_name": {"type": "string"},
                    "company": {"type": "string"},
                    "domain": {"type": "string"},
                },
                "required": ["first_name", "last_name"],
            },
        ),
        types.Tool(
            name="verify_email",
            description="Check if an email is deliverable — requires Hunter.io (currently restricted)",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {"type": "string"},
                },
                "required": ["email"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name == "enrich_company":
        result = await _enrich_company(arguments)
        return [types.TextContent(type="text", text=result)]
    elif name == "enrich_contact":
        return [types.TextContent(type="text", text=
            f"Contact lookup for {arguments.get('first_name')} {arguments.get('last_name')} @ {arguments.get('company', '?')}\n\n"
            "⚠️  Apollo people search requires a paid plan and Hunter.io is restricted.\n"
            "To find contact emails, upgrade your plan or use: LinkedIn, Lusha, ZoomInfo."
        )]
    elif name == "verify_email":
        return [types.TextContent(type="text", text=
            f"Email verification for {arguments.get('email')}\n\n"
            "⚠️  Hunter.io account is currently restricted.\n"
            "Alternatives: NeverBounce, ZeroBounce, or upgrade Hunter."
        )]
    raise ValueError(f"Unknown tool: {name}")


async def _enrich_company(args: dict) -> str:
    domain = args.get("domain", "")
    company = args.get("company", "")

    payload: dict[str, Any] = {"per_page": 1}
    if domain:
        payload["q_organization_domains"] = [domain]
    elif company:
        payload["q_organization_name"] = company
    else:
        return "Provide a domain or company name."

    headers = {"Content-Type": "application/json", "x-api-key": APOLLO_API_KEY}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post("https://api.apollo.io/v1/organizations/search", json=payload, headers=headers)
        if resp.status_code != 200:
            return f"Apollo API error ({resp.status_code})"

        orgs = resp.json().get("organizations", [])
        if not orgs:
            return "No company found."

        org = orgs[0]
        tech = org.get("technology_names", []) or []
        funding = org.get("funding_events", [])
        rev = org.get("estimated_revenue", {})
        rev_str = f"${rev['value']:,.0f}" if isinstance(rev, dict) and rev.get("value") else "N/A"
        keywords = org.get("keywords", []) or []

        return (
            f"📊 {org.get('name', 'N/A')}\n"
            f"   Domain: {org.get('primary_domain', 'N/A')}\n"
            f"   Employees: {org.get('estimated_num_employees', '?')}\n"
            f"   Revenue: {rev_str}\n"
            f"   Founded: {org.get('founded_year', '?')}\n"
            f"   Industry: {', '.join(org.get('industry_tags', [])[:4]) or '?'}\n"
            f"   Funding: {len(funding)} rounds\n"
            f"   Tech Stack: {', '.join(tech[:8]) if tech else '?'}\n"
            f"   Keywords: {', '.join(keywords[:8]) if keywords else '?'}\n"
            f"   LinkedIn: {org.get('linkedin_url', 'N/A')}\n"
            f"   Description: {(org.get('short_description', '') or '')[:300]}"
        )


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, InitializationOptions(
            server_name="enrichment", server_version="0.1.0",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            ),
        ))


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())