#!/bin/bash
# Wrapper script for Hyperliquid MCP server
# Loads environment from .env file if present

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load .env if it exists
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

# Default to mainnet if not set
export HYPERLIQUID_TESTNET="${HYPERLIQUID_TESTNET:-false}"

# Validate required env vars
if [ -z "$HYPERLIQUID_PRIVATE_KEY" ]; then
    echo "❌ HYPERLIQUID_PRIVATE_KEY is required. Copy .env.example to .env and fill in your values."
    exit 1
fi

if [ -z "$HYPERLIQUID_ACCOUNT_ADDRESS" ]; then
    echo "❌ HYPERLIQUID_ACCOUNT_ADDRESS is required."
    exit 1
fi

cd "$SCRIPT_DIR"
exec python3 main.py
