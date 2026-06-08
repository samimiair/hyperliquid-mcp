# Hyperliquid MCP Server 🚀

**Model Context Protocol (MCP) server for Hyperliquid** — 48 tools for trading, monitoring, risk management, and security on the Hyperliquid perpetual DEX.

Built on the official [`hyperliquid-python-sdk`](https://github.com/hyperliquid-dex/hyperliquid-python-sdk) with production-grade error handling.

---

## Features

### 📡 Tier 1 — Monitoring (15 tools)
- Real-time user state, positions, balances
- Open orders, trade history, funding history
- Market data: mid prices, L2 order book, candlesticks
- Sub-accounts, staking, fee structure

### 💹 Tier 2 — Trading (10 tools)
- Limit, market, and trigger orders
- Bracket orders (entry + TP + SL)
- Position management: modify, close, leverage
- Funding rate impact calculator

### ⚠️ Tier 3 — Risk Management (10 tools)
- Order risk validation before execution
- Liquidation price estimation
- Margin health monitoring
- Portfolio health check & simulation
- Auto leverage adjustment

### 🔒 Tier 4 — Security (8 tools)
- Wallet & configuration validation
- Preflight checks before trading
- API Wallet / Agent Mode setup
- Trading limits, rate limiting
- Audit trail & emergency stop

### 📊 Bonus Analytics (5 tools)
- Position analysis with P&L and risk scoring
- Performance metrics (win rate, Sharpe, drawdown)
- Multi-coin comparison
- Strategy backtesting (MA/RSI/Momentum)
- Market sentiment analysis

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/samimiair/hyperliquid-mcp.git
cd hyperliquid-mcp
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your wallet details:
#   HYPERLIQUID_PRIVATE_KEY=your_64_char_hex_key
#   HYPERLIQUID_ACCOUNT_ADDRESS=0xYourWalletAddress
```

### 3. Run

```bash
./run.sh
```

Or run directly with Hermes:

```bash
hermes mcp add hyperliquid --command /path/to/hyperliquid-mcp/run.sh
hermes config set mcp_servers.hyperliquid.cwd /path/to/hyperliquid-mcp
hermes config set mcp_servers.hyperliquid.timeout 120
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `HYPERLIQUID_PRIVATE_KEY` | ✅ | Your wallet private key (64 hex chars) |
| `HYPERLIQUID_ACCOUNT_ADDRESS` | ✅ | Your wallet address (0x...) |
| `HYPERLIQUID_API_WALLET` | ❌ | API wallet for Agent Mode |
| `HYPERLIQUID_TESTNET` | ❌ | Set to `"true"` for testnet (default: mainnet) |

---

## Architecture

```
hyperliquid-mcp/
├── main.py            # MCP server entry point (48 tools)
├── api_client.py      # Hyperliquid API wrapper (SDK-based)
├── trading.py         # Order placement & management
├── monitoring.py      # Market data & state queries
├── risk_mgmt.py       # Risk validation & simulation
├── security.py        # Wallet & configuration checks
├── validators.py      # Input validation
├── rate_limiter.py    # API rate limiting
├── alert_manager.py   # Error & alert handling
├── wallet.py          # (Deprecated) Legacy wallet code
├── run.sh             # Startup script with env validation
├── .env.example       # Configuration template
└── requirements.txt   # Dependencies
```

---

## Security

- **Never commit your `.env` file** — it's in `.gitignore`
- All secrets are read from environment variables
- The `run.sh` script validates required env vars before starting
- Use **API Wallet / Agent Mode** to limit trading permissions
- Emergency stop tool (`emergency_stop`) closes all positions instantly

---

## License

MIT
