#!/bin/bash
# Channel Tools - Setup Script
# Run this from the repo root to set up all MCP servers

set -e

echo "=== Channel Tools Setup ==="

# Python setup
for server in lead-gen enrichment outreach channel-mgmt; do
    echo "Setting up mcp-servers/$server..."
    cd "mcp-servers/$server"
    python3 -m venv .venv 2>/dev/null || python3 -m venv venv 2>/dev/null
    cd ../..
done

echo "=== Done ==="
