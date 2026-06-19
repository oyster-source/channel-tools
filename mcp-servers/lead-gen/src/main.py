"""MCP Server: Lead Generation & Qualification

Tools:
- search_companies: Search for companies by criteria
- qualify_lead: Score and qualify a lead
- find_contacts: Find decision-makers at a company
"""

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types
from typing import Any
import httpx

server = Server("lead-gen")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_companies",
            description="Search for companies matching criteria (industry, size, location)",
            inputSchema={
                "type": "object",
                "properties": {
                    "industry": {"type": "string", "description": "Target industry (e.g. cybersecurity, SaaS)"},
                    "min_employees": {"type": "integer", "description": "Minimum company size"},
                    "location": {"type": "string", "description": "Location/region filter"},
                    "keywords": {"type": "string", "description": "Search keywords for company description"},
                },
                "required": [],
            },
        ),
        types.Tool(
            name="qualify_lead",
            description="Score and qualify a lead based on BANT or similar criteria",
            inputSchema={
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "Company name"},
                    "budget": {"type": "string", "description": "Estimated budget range"},
                    "authority": {"type": "string", "description": "Decision-maker contact"},
                    "need": {"type": "string", "description": "Identified need/pain point"},
                    "timeline": {"type": "string", "description": "Purchase timeline"},
                },
                "required": ["company"],
            },
        ),
        types.Tool(
            name="find_contacts",
            description="Find key contacts/decision-makers at a target company",
            inputSchema={
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "Company name"},
                    "domain": {"type": "string", "description": "Company domain"},
                    "role": {"type": "string", "description": "Target role (e.g. CTO, VP Sales)"},
                },
                "required": ["company"],
            },
        ),
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name == "search_companies":
        # TODO: Integrate with Apollo/Clearbit/Hunter APIs
        return [types.TextContent(type="text", content=f"Searching companies matching: {arguments}")]
    elif name == "qualify_lead":
        score = _calculate_lead_score(arguments)
        return [types.TextContent(type="text", content=f"Lead qualification for {arguments.get('company')}:\nScore: {score}/100")]
    elif name == "find_contacts":
        # TODO: Integrate with Apollo/Hunter API
        return [types.TextContent(type="text", content=f"Finding contacts at {arguments.get('company')}")]
    raise ValueError(f"Unknown tool: {name}")

def _calculate_lead_score(args: dict) -> int:
    score = 50
    if args.get("budget"): score += 15
    if args.get("authority"): score += 15
    if args.get("need"): score += 10
    if args.get("timeline"): score += 10
    return min(score, 100)

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            InitializationOptions(
                server_name="lead-gen",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
