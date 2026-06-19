# Channel Tools

MCP-driven tools for **lead generation, outreach, enrichment, and partner/channel management.**

## Architecture

```
channel-tools/
├── mcp-servers/
│   ├── lead-gen/      # MCP: Lead sourcing & qualification
│   ├── enrichment/    # MCP: Contact & company data enrichment
│   ├── outreach/      # MCP: Sequence & campaign management
│   └── channel-mgmt/  # MCP: Partner/channel management
├── micro-apps/        # Frontend UIs and dashboards
├── docs/              # Setup and deployment guides
└── scripts/           # Automation helpers
```

## MCP Servers

Each server exposes tools via the [Model Context Protocol](https://modelcontextprotocol.io).

| Server | Tools | Integrations (planned) |
|--------|-------|----------------------|
| **lead-gen** | `search_companies`, `qualify_lead`, `find_contacts` | Apollo.io, Clearbit, LinkedIn |
| **enrichment** | `enrich_contact`, `enrich_company`, `verify_email` | Hunter.io, Apollo.io, NeverBounce |
| **outreach** | `create_sequence`, `personalize_message`, `track_campaign` | Gmail, LinkedIn, HubSpot |
| **channel-mgmt** | `onboard_partner`, `track_deal_reg`, `evaluate_partner`, `find_partners` | CRM, PartnerStack, Impartner |

## Quick Start

```bash
# Clone
git clone https://github.com/oyster-source/channel-tools.git
cd channel-tools

# Set up a server (e.g. lead-gen)
cd mcp-servers/lead-gen
python3 -m venv .venv
source .venv/bin/activate
uv pip install mcp httpx

# Run the server
python3 src/main.py
```

## Running with Hermes Agent

Add to your `config.yaml`:

```yaml
mcp_servers:
  lead-gen:
    command: python3
    args: ["src/main.py"]
    cwd: "/path/to/channel-tools/mcp-servers/lead-gen"
```

## Roadmap

- [ ] API integrations (Apollo, Hunter, Clearbit)
- [ ] Webhook triggers (inbound lead capture)
- [ ] Micro-app dashboards
- [ ] Docker deployment
- [ ] CI/CD pipeline
