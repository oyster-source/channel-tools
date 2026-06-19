"""MCP Server: Data Enrichment

Tools:
- enrich_contact: Enrich a contact with email, social, and company data
- enrich_company: Enrich company data (employees, funding, tech stack)
- verify_email: Verify email deliverability
"""

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types
from typing import Any

server = Server("enrichment")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="enrich_contact",
            description="Enrich contact info: email, phone, social profiles, current role",
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
            name="enrich_company",
            description="Enrich company profile: size, funding, tech stack, recent news",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Company website domain"},
                    "company": {"type": "string", "description": "Company name (fallback)"},
                },
                "required": [],
            },
        ),
        types.Tool(
            name="verify_email",
            description="Verify if an email address is deliverable",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Email to verify"},
                },
                "required": ["email"],
            },
        ),
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name == "enrich_contact":
        return [types.TextContent(type="text", content=f"Enriching contact: {arguments.get('first_name')} {arguments.get('last_name')} @ {arguments.get('company', '?')}")]
    elif name == "enrich_company":
        return [types.TextContent(type="text", content=f"Enriching company: {arguments.get('company') or arguments.get('domain')}")]
    elif name == "verify_email":
        return [types.TextContent(type="text", content=f"Verifying email: {arguments.get('email')}")]
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            InitializationOptions(
                server_name="enrichment",
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
