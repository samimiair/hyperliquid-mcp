#!/usr/bin/env python3
"""
Hyperliquid MCP Server – 49 tools across 4 tiers for trading, monitoring, risk, and security
"""
import os
import json
import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime
from dotenv import load_dotenv

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

load_dotenv()

from api_client import HyperliquidAPI
from validators import InputValidator
from rate_limiter import RateLimiter
from alert_manager import AlertManager
from monitoring import MonitoringTools
from trading import TradingTools
from risk_mgmt import RiskManagementTools
from security import SecurityTools

server = Server("hyperliquid-mcp")

# Global instances
api: Optional[HyperliquidAPI] = None
monitoring: Optional[MonitoringTools] = None
trading: Optional[TradingTools] = None
risk_mgmt: Optional[RiskManagementTools] = None
security: Optional[SecurityTools] = None
rate_limiter: Optional[RateLimiter] = None
alert_manager: Optional[AlertManager] = None
validator = InputValidator()


def _tool(name: str, desc: str, props: dict, required: Optional[list] = None) -> Tool:
    return Tool(name=name, description=desc, inputSchema={"type": "object", "properties": props, "required": required or []})


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # ── TIER 1: MONITORING ──
        _tool("get_user_state", "Fetch user positions, margin, balances", {
            "account_address": {"type": "string", "description": "Account address (optional)"},
            "check_spot": {"type": "boolean", "description": "Include spot (default: false)"},
        }),
        _tool("get_user_open_orders", "Get all open orders", {
            "account_address": {"type": "string", "description": "Account address (optional)"},
        }),
        _tool("get_user_trade_history", "Get trade fill history", {
            "account_address": {"type": "string", "description": "Account address (optional)"},
            "limit": {"type": "integer", "description": "Max records (default: 100)"},
        }),
        _tool("get_user_funding_history", "Query funding payment history", {
            "account_address": {"type": "string"}, "start_time": {"type": "string"},
            "end_time": {"type": "string"}, "limit": {"type": "integer", "default": 100},
        }),
        _tool("get_user_fees", "Get user fee structure", {
            "account_address": {"type": "string", "description": "Account address (optional)"},
        }),
        _tool("get_user_staking_summary", "Get staking details and rewards", {
            "account_address": {"type": "string", "description": "Account address (optional)"},
        }),
        _tool("get_user_order_by_oid", "Get specific order by ID", {
            "account_address": {"type": "string"}, "oid": {"type": "string"},
        }, required=["account_address", "oid"]),
        _tool("get_user_sub_accounts", "List sub-accounts", {
            "account_address": {"type": "string"},
        }),
        _tool("get_all_mids", "Get mid prices for all pairs", {}),
        _tool("get_l2_snapshot", "Get L2 order book snapshot", {
            "coin": {"type": "string", "description": "Coin (BTC, ETH, etc)"},
        }, required=["coin"]),
        _tool("get_candles_snapshot", "Get candlestick data", {
            "coin": {"type": "string"}, "interval": {"type": "string", "enum": ["1m","5m","15m","1h","4h","1d"], "default": "1h"},
            "start_time": {"type": "string"}, "end_time": {"type": "string"},
        }, required=["coin"]),
        _tool("get_coin_funding_history", "Get funding rate history for coin", {
            "coin": {"type": "string"}, "start_time": {"type": "string"}, "end_time": {"type": "string"}, "limit": {"type": "integer", "default": 100},
        }, required=["coin"]),
        _tool("get_perp_metadata", "Get perpetual market metadata", {
            "include_asset_ctxs": {"type": "boolean", "default": False},
        }),
        _tool("get_spot_metadata", "Get spot market metadata", {
            "include_asset_ctxs": {"type": "boolean", "default": False},
        }),
        # ── TIER 2: TRADING ──
        _tool("place_order", "Place limit/market order with validation", {
            "coin": {"type": "string"}, "is_buy": {"type": "boolean"}, "size": {"type": "number"},
            "price": {"type": "number", "description": "Limit price (0 for market)"},
            "leverage": {"type": "integer", "default": 1},
            "order_type": {"type": "string", "enum": ["limit","market","trigger"], "default": "limit"},
            "tif": {"type": "string", "enum": ["Ioc","Gtc","PostOnly"], "default": "Ioc"},
            "reduce_only": {"type": "boolean", "default": False},
        }, required=["coin","is_buy","size","price"]),
        _tool("place_bracket_order", "Entry + TP + SL bracket", {
            "coin": {"type": "string"}, "is_buy": {"type": "boolean"}, "entry_price": {"type": "number"},
            "size": {"type": "number"}, "take_profit": {"type": "number"}, "stop_loss": {"type": "number"},
            "leverage": {"type": "integer", "default": 1},
        }, required=["coin","is_buy","entry_price","size","take_profit","stop_loss"]),
        _tool("modify_order", "Modify order price/size", {
            "coin": {"type": "string"}, "oid": {"type": "string"},
            "new_price": {"type": "number"}, "new_size": {"type": "number"},
        }, required=["coin","oid"]),
        _tool("cancel_order", "Cancel specific order", {
            "coin": {"type": "string"}, "oid": {"type": "string"},
        }, required=["coin","oid"]),
        _tool("cancel_all_orders", "Cancel all open orders", {
            "coin": {"type": "string", "description": "Specific coin (optional)"},
        }),
        _tool("get_position_by_coin", "Get position details for coin", {
            "coin": {"type": "string"}, "account_address": {"type": "string"},
        }, required=["coin"]),
        _tool("close_position", "Close position with market order", {
            "coin": {"type": "string"}, "amount_to_close": {"type": "number"},
        }, required=["coin"]),
        _tool("update_leverage", "Change leverage for coin", {
            "coin": {"type": "string"}, "leverage": {"type": "integer", "description": "1-50"},
            "is_cross": {"type": "boolean", "default": False},
        }, required=["coin","leverage"]),
        _tool("get_funding_history", "Get funding payments (alias)", {
            "account_address": {"type": "string"}, "start_time": {"type": "string"},
            "end_time": {"type": "string"}, "limit": {"type": "integer", "default": 100},
        }),
        _tool("calculate_funding_impact", "Estimate funding cost for position", {
            "coin": {"type": "string"}, "size": {"type": "number"}, "days": {"type": "number", "default": 1},
        }, required=["coin","size"]),
        # ── TIER 3: RISK ──
        _tool("validate_order_risk", "Check order risk before placing", {
            "coin": {"type": "string"}, "is_buy": {"type": "boolean"}, "size": {"type": "number"},
            "price": {"type": "number"}, "leverage": {"type": "integer", "default": 1},
        }, required=["coin","is_buy","size","price"]),
        _tool("estimate_liquidation_price", "Calculate liquidation price", {
            "coin": {"type": "string"}, "is_buy": {"type": "boolean"}, "entry_price": {"type": "number"},
            "size": {"type": "number"}, "leverage": {"type": "integer", "default": 1},
        }, required=["coin","is_buy","entry_price","size"]),
        _tool("check_margin_health", "Check margin usage and available balance", {
            "account_address": {"type": "string"}, "warning_threshold": {"type": "number", "default": 80},
        }),
        _tool("auto_adjust_leverage", "Auto-reduce leverage if risk too high", {
            "coin": {"type": "string"}, "max_margin_usage": {"type": "number", "default": 70},
            "require_confirmation": {"type": "boolean", "default": True},
        }),
        _tool("position_monitor", "Start real-time position monitoring", {
            "coin": {"type": "string"}, "check_interval": {"type": "integer", "default": 10},
            "liquidation_threshold": {"type": "number", "default": 10},
            "auto_reduce": {"type": "boolean", "default": False},
        }),
        _tool("stop_monitoring", "Stop a running position monitor", {
            "task_id": {"type": "string", "description": "Task ID from position_monitor. Omit to stop all."},
        }),
        _tool("liquidation_alert", "Set liquidation alert threshold", {
            "coin": {"type": "string"}, "threshold_pct": {"type": "number", "default": 10},
            "enable": {"type": "boolean", "default": True},
        }),
        _tool("funding_rate_impact", "Calculate funding cost impact", {
            "coin": {"type": "string"}, "size": {"type": "number"}, "entry_price": {"type": "number"},
            "hours": {"type": "number", "default": 1},
        }, required=["coin","size","entry_price"]),
        _tool("portfolio_health_check", "Full portfolio risk analysis", {
            "account_address": {"type": "string"},
            "include_liquidation_risk": {"type": "boolean", "default": True},
            "include_funding_impact": {"type": "boolean", "default": True},
        }),
        _tool("simulate_order_impact", "Simulate order impact on portfolio", {
            "coin": {"type": "string"}, "is_buy": {"type": "boolean"}, "size": {"type": "number"},
            "price": {"type": "number"}, "leverage": {"type": "integer", "default": 1},
        }, required=["coin","is_buy","size","price"]),
        _tool("simulate_close_price", "Best way to close position", {
            "coin": {"type": "string"}, "account_address": {"type": "string"},
        }, required=["coin"]),
        # ── TIER 4: SECURITY ──
        _tool("validate_configuration", "Validate wallet keys and addresses", {
            "check_balance": {"type": "boolean", "default": True},
            "min_balance_usd": {"type": "number", "default": 100},
        }),
        _tool("preflight_check", "Run all pre-trading checks", {
            "verbose": {"type": "boolean", "default": True},
        }),
        _tool("setup_agent_mode", "Setup API wallet for safer trading", {
            "max_trade_size": {"type": "number"},
        }),
        _tool("testnet_workflow", "Setup testnet and run test trades", {
            "test_coin": {"type": "string", "default": "BTC"}, "test_size": {"type": "number", "default": 0.001},
        }),
        _tool("set_trading_limits", "Configure trading limits", {
            "max_order_size_usd": {"type": "number"}, "max_daily_notional": {"type": "number"},
            "max_leverage": {"type": "integer"}, "max_margin_usage_pct": {"type": "number"},
            "trading_hours_only": {"type": "boolean", "default": False},
        }),
        _tool("rate_limit_handler", "Configure API rate limiting", {
            "max_requests_per_minute": {"type": "integer", "default": 60},
            "enable_queuing": {"type": "boolean", "default": True},
        }),
        _tool("audit_trail", "View/export audit trail", {
            "export_format": {"type": "string", "enum": ["json","csv","text"], "default": "json"},
            "start_time": {"type": "string"}, "end_time": {"type": "string"},
        }),
        _tool("emergency_stop", "EMERGENCY: close all positions & cancel all orders", {
            "confirm": {"type": "boolean", "default": False, "description": "Set true to confirm"},
        }),
        # ── BONUS ANALYTICS ──
        _tool("analyze_positions", "AI-assisted P&L, risk, and recommendations", {
            "account_address": {"type": "string"}, "detailed": {"type": "boolean", "default": True},
        }),
        _tool("performance_metrics", "Win rate, P&L, trade statistics", {
            "account_address": {"type": "string"}, "start_time": {"type": "string"}, "end_time": {"type": "string"},
        }),
        _tool("coin_comparison", "Compare multiple coins", {
            "coins": {"type": "array", "items": {"type": "string"}},
            "metrics": {"type": "string", "default": "funding"},
        }, required=["coins"]),
        _tool("backtest_strategy", "Backtest MA/RSI/momentum strategy", {
            "coin": {"type": "string"}, "strategy": {"type": "string", "enum": ["moving_average","rsi","momentum"]},
            "start_time": {"type": "string"}, "end_time": {"type": "string"},
            "interval": {"type": "string", "default": "1h"},
        }, required=["coin","strategy","start_time","end_time"]),
        _tool("get_market_sentiment", "Market sentiment analysis", {
            "coin": {"type": "string"}, "timeframe": {"type": "string", "enum": ["1h","1d","7d"], "default": "1d"},
        }),
        _tool("optimize_portfolio", "Portfolio optimization suggestions", {
            "account_address": {"type": "string"},
            "strategy": {"type": "string", "enum": ["conservative","balanced","aggressive"], "default": "balanced"},
        }),
    ]


@server.call_tool()
async def handle_call(name: str, arguments: dict) -> list[TextContent]:
    try:
        args = arguments or {}
        if not await rate_limiter.check_limit():
            return [TextContent(type="text", text="❌ Rate limit exceeded. Request queued.")]

        # ── TIER 1 ──
        if name == "get_user_state":
            r = await monitoring.get_user_state(args.get("account_address"), args.get("check_spot", False))
        elif name == "get_user_open_orders":
            r = await monitoring.get_user_open_orders(args.get("account_address"))
        elif name == "get_user_trade_history":
            r = await monitoring.get_user_trade_history(args.get("account_address"), args.get("limit", 100))
        elif name == "get_user_funding_history":
            r = await monitoring.get_user_funding_history(args.get("account_address"), args.get("start_time"), args.get("end_time"), args.get("limit", 100))
        elif name == "get_user_fees":
            r = await monitoring.get_user_fees(args.get("account_address"))
        elif name == "get_user_staking_summary":
            r = await monitoring.get_user_staking_summary(args.get("account_address"))
        elif name == "get_user_order_by_oid":
            r = await monitoring.get_user_order_by_oid(args["account_address"], args["oid"])
        elif name == "get_user_sub_accounts":
            r = await monitoring.get_user_sub_accounts(args.get("account_address"))
        elif name == "get_all_mids":
            r = await monitoring.get_all_mids()
        elif name == "get_l2_snapshot":
            r = await monitoring.get_l2_snapshot(args["coin"])
        elif name == "get_candles_snapshot":
            r = await monitoring.get_candles_snapshot(args["coin"], args.get("interval", "1h"), args.get("start_time"), args.get("end_time"))
        elif name == "get_coin_funding_history":
            r = await monitoring.get_coin_funding_history(args["coin"], args.get("start_time"), args.get("end_time"), args.get("limit", 100))
        elif name == "get_perp_metadata":
            r = await monitoring.get_perp_metadata(args.get("include_asset_ctxs", False))
        elif name == "get_spot_metadata":
            r = await monitoring.get_spot_metadata(args.get("include_asset_ctxs", False))

        # ── TIER 2 ──
        elif name == "place_order":
            r = await trading.place_order(args["coin"], args["is_buy"], args["size"], args["price"],
                args.get("leverage", 1), args.get("order_type", "limit"), args.get("tif", "Ioc"), args.get("reduce_only", False))
        elif name == "place_bracket_order":
            r = await trading.place_bracket_order(args["coin"], args["is_buy"], args["entry_price"], args["size"],
                args["take_profit"], args["stop_loss"], args.get("leverage", 1))
        elif name == "modify_order":
            r = await trading.modify_order(args["coin"], args["oid"], args.get("new_price"), args.get("new_size"))
        elif name == "cancel_order":
            r = await trading.cancel_order(args["coin"], args["oid"])
        elif name == "cancel_all_orders":
            r = await trading.cancel_all_orders(args.get("coin"))
        elif name == "get_position_by_coin":
            r = await trading.get_position_by_coin(args["coin"], args.get("account_address"))
        elif name == "close_position":
            r = await trading.close_position(args["coin"], args.get("amount_to_close"))
        elif name == "update_leverage":
            r = await trading.update_leverage(args["coin"], args["leverage"], args.get("is_cross", False))
        elif name == "get_funding_history":
            r = await trading.get_funding_history(args.get("account_address"), args.get("start_time"), args.get("end_time"), args.get("limit", 100))
        elif name == "calculate_funding_impact":
            r = await trading.calculate_funding_impact(args["coin"], args["size"], args.get("days", 1))

        # ── TIER 3 ──
        elif name == "validate_order_risk":
            r = await risk_mgmt.validate_order_risk(args["coin"], args["is_buy"], args["size"], args["price"], args.get("leverage", 1))
        elif name == "estimate_liquidation_price":
            r = await risk_mgmt.estimate_liquidation_price(args["coin"], args["is_buy"], args["entry_price"], args["size"], args.get("leverage", 1))
        elif name == "check_margin_health":
            r = await risk_mgmt.check_margin_health(args.get("account_address"), args.get("warning_threshold", 80))
        elif name == "auto_adjust_leverage":
            r = await risk_mgmt.auto_adjust_leverage(args.get("coin"), args.get("max_margin_usage", 70), args.get("require_confirmation", True))
        elif name == "position_monitor":
            r = await risk_mgmt.position_monitor(args.get("coin"), args.get("check_interval", 10), args.get("liquidation_threshold", 10), args.get("auto_reduce", False))
        elif name == "stop_monitoring":
            r = await risk_mgmt.stop_monitoring(args.get("task_id"))
        elif name == "liquidation_alert":
            r = await risk_mgmt.liquidation_alert(args.get("coin"), args.get("threshold_pct", 10), args.get("enable", True))
        elif name == "funding_rate_impact":
            r = await risk_mgmt.funding_rate_impact(args["coin"], args["size"], args["entry_price"], args.get("hours", 1))
        elif name == "portfolio_health_check":
            r = await risk_mgmt.portfolio_health_check(args.get("account_address"), args.get("include_liquidation_risk", True), args.get("include_funding_impact", True))
        elif name == "simulate_order_impact":
            r = await risk_mgmt.simulate_order_impact(args["coin"], args["is_buy"], args["size"], args["price"], args.get("leverage", 1))
        elif name == "simulate_close_price":
            r = await risk_mgmt.simulate_close_price(args["coin"], args.get("account_address"))

        # ── TIER 4 ──
        elif name == "validate_configuration":
            r = await security.validate_configuration(args.get("check_balance", True), args.get("min_balance_usd", 100))
        elif name == "preflight_check":
            r = await security.preflight_check(args.get("verbose", True))
        elif name == "setup_agent_mode":
            r = await security.setup_agent_mode(args.get("max_trade_size"))
        elif name == "testnet_workflow":
            r = await security.testnet_workflow(args.get("test_coin", "BTC"), args.get("test_size", 0.001))
        elif name == "set_trading_limits":
            r = await security.set_trading_limits(args.get("max_order_size_usd"), args.get("max_daily_notional"),
                args.get("max_leverage"), args.get("max_margin_usage_pct"), args.get("trading_hours_only", False))
        elif name == "rate_limit_handler":
            r = await rate_limiter.configure(args.get("max_requests_per_minute", 60), args.get("enable_queuing", True))
        elif name == "audit_trail":
            r = await security.audit_trail(args.get("export_format", "json"), args.get("start_time"), args.get("end_time"))
        elif name == "emergency_stop":
            if not args.get("confirm"):
                r = {"error": "❌ Confirmation required. Set confirm=true"}
            else:
                r = await risk_mgmt.emergency_stop()

        # ── BONUS ──
        elif name == "analyze_positions":
            r = await monitoring.analyze_positions(args.get("account_address"), args.get("detailed", True))
        elif name == "performance_metrics":
            r = await monitoring.performance_metrics(args.get("account_address"), args.get("start_time"), args.get("end_time"))
        elif name == "coin_comparison":
            r = await monitoring.coin_comparison(args["coins"], args.get("metrics", "funding"))
        elif name == "backtest_strategy":
            r = await monitoring.backtest_strategy(args["coin"], args["strategy"], args["start_time"], args["end_time"], args.get("interval", "1h"))
        elif name == "get_market_sentiment":
            r = await monitoring.get_market_sentiment(args.get("coin"), args.get("timeframe", "1d"))
        elif name == "optimize_portfolio":
            r = await monitoring.optimize_portfolio(args.get("account_address"), args.get("strategy", "balanced"))
        else:
            r = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(r, indent=2, default=str))]

    except Exception as e:
        err = f"❌ Error in {name}: {e}"
        await alert_manager.send_alert("ERROR", name, str(e))
        return [TextContent(type="text", text=json.dumps({"error": err}, indent=2))]


async def main():
    global api, monitoring, trading, risk_mgmt, security, rate_limiter, alert_manager

    private_key = os.getenv("HYPERLIQUID_PRIVATE_KEY")
    account_address = os.getenv("HYPERLIQUID_ACCOUNT_ADDRESS")
    api_wallet = os.getenv("HYPERLIQUID_API_WALLET") or account_address
    testnet = os.getenv("HYPERLIQUID_TESTNET", "false").lower() == "true"

    if not private_key:
        print("❌ HYPERLIQUID_PRIVATE_KEY not set in .env")
        return
    if not account_address:
        print("❌ HYPERLIQUID_ACCOUNT_ADDRESS not set in .env")
        return

    api = HyperliquidAPI(
        private_key=private_key,
        account_address=account_address,
        vault_address=api_wallet,
        testnet=testnet,
    )
    rate_limiter = RateLimiter(max_per_minute=60)
    alert_manager = AlertManager()
    monitoring = MonitoringTools(api)
    trading = TradingTools(api)
    risk_mgmt = RiskManagementTools(api, alert_manager)
    security = SecurityTools(api)

    async with stdio_server() as (read_stream, write_stream):
        print(f"✅ Hyperliquid MCP started", flush=True)
        print(f"🌐 {'Testnet' if testnet else 'Mainnet'}", flush=True)
        print(f"👤 Main: {account_address[:10]}...", flush=True)
        print(f"🤖 API Wallet: {api_wallet[:10]}...", flush=True)
        print(f"📡 49 tools ready...", flush=True)
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
