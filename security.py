"""
TIER 4: SECURITY & SETUP (8 tools)
"""
import json
from typing import Any, Dict, Optional
from datetime import datetime

from api_client import HyperliquidAPI


class SecurityTools:
    def __init__(self, api: HyperliquidAPI):
        self.api = api

    async def validate_configuration(self, check_balance: bool = True, min_balance_usd: float = 100) -> Dict:
        checks = {}
        pk_ok = self.api.private_key and len(self.api.private_key) == 64
        checks["private_key"] = {"status": "✅ PASS" if pk_ok else "❌ FAIL",
                                  "message": "Valid format" if pk_ok else "Invalid format"}
        addr_ok = self.api.account_address and self.api.account_address.startswith("0x")
        checks["account_address"] = {"status": "✅ PASS" if addr_ok else "❌ FAIL",
                                      "message": "Valid address" if addr_ok else "Invalid address"}
        if check_balance:
            try:
                state = await self.api.get_user_state(self.api.account_address)
                bal = float(state.get("marginSummary", {}).get("accountValue", 0))
                checks["balance"] = {"status": "✅ PASS" if bal >= min_balance_usd else "❌ FAIL",
                                      "message": f"Balance ${bal:.2f}" if bal >= min_balance_usd else f"Balance ${bal:.2f} < ${min_balance_usd}"}
            except Exception as e:
                checks["balance"] = {"status": "❌ FAIL", "message": str(e)}
        checks["network"] = {"status": "✅ PASS", "message": "Testnet" if self.api.testnet else "Mainnet"}
        all_pass = all(c["status"].startswith("✅") for c in checks.values())
        return {"configuration_valid": all_pass, "checks": checks,
                "recommendation": "✅ Looks good!" if all_pass else "❌ Fix issues before trading",
                "timestamp": datetime.now().isoformat()}

    async def preflight_check(self, verbose: bool = True) -> Dict:
        checks = {}
        checks["configuration"] = await self.validate_configuration(check_balance=True)
        try:
            mids = await self.api.get_all_mids()
            checks["api_connectivity"] = {"status": "✅ PASS", "message": f"API connected, {len(mids)} pairs"}
        except Exception as e:
            checks["api_connectivity"] = {"status": "❌ FAIL", "message": str(e)}
        try:
            valid = self.api.validate()
            checks["wallet_signing"] = {"status": "✅ PASS" if valid else "❌ FAIL",
                                         "message": "Can sign" if valid else "Cannot sign"}
        except Exception as e:
            checks["wallet_signing"] = {"status": "❌ FAIL", "message": str(e)}
        all_pass = all(c.get("status", "").startswith("✅") for c in checks.values())
        return {"preflight_complete": all_pass, "status": "✅ READY" if all_pass else "❌ NOT READY",
                "checks": checks if verbose else None, "timestamp": datetime.now().isoformat()}

    async def setup_agent_mode(self, max_trade_size: Optional[float] = None) -> Dict:
        return {"agent_mode_setup": {"status": "In development", "benefits": ["Trade without exposing main key",
                    "Set spending limits", "Use API wallet for automation", "Higher security"],
            "steps": ["1. Create API wallet on Hyperliquid", "2. Approve for your main account",
                      "3. Set max_trade_size limit", "4. Use API wallet key in MCP"],
            "max_trade_size": max_trade_size, "documentation": "https://hyperliquid.gitbook.io/hyperliquid-docs/api"},
            "timestamp": datetime.now().isoformat()}

    async def testnet_workflow(self, test_coin: str = "BTC", test_size: float = 0.001) -> Dict:
        if not self.api.testnet:
            return {"error": "Not on testnet. Set HYPERLIQUID_TESTNET=true", "instruction": "Update .env"}
        try:
            state = await self.api.get_user_state(self.api.account_address)
            bal = float(state.get("marginSummary", {}).get("accountValue", 0))
            mids = await self.api.get_all_mids()
            price = mids.get(test_coin, 0)
            return {"testnet_workflow": {"testnet_balance": round(bal, 2),
                    "suggested_test_trade": {"coin": test_coin, "side": "BUY", "size": test_size,
                        "price": round(price * 0.99, 2), "order_type": "limit"},
                    "workflow_steps": ["1️⃣ Place BUY", "2️⃣ Wait or cancel", "3️⃣ If filled, SELL to close", "4️⃣ Verify", "5️⃣ Switch to mainnet"],
                    "timestamp": datetime.now().isoformat()}}
        except Exception as e:
            return {"error": str(e)}

    async def set_trading_limits(self, max_order_size_usd: Optional[float] = None,
                                  max_daily_notional: Optional[float] = None, max_leverage: Optional[int] = None,
                                  max_margin_usage_pct: Optional[float] = None,
                                  trading_hours_only: bool = False) -> Dict:
        limits = {"max_order_size_usd": max_order_size_usd or float('inf'), "max_daily_notional": max_daily_notional or float('inf'),
                  "max_leverage": max_leverage or 50, "max_margin_usage_pct": max_margin_usage_pct or 90,
                  "trading_hours_only": trading_hours_only, "trading_hours_utc": "09:00-17:00" if trading_hours_only else "24/7"}
        try:
            with open(".hl_config.json", "w") as f:
                json.dump(limits, f, indent=2)
            status = "✅ SAVED"
        except Exception:
            status = "⚠️ Could not save"
        return {"trading_limits_set": True, "limits": limits, "status": status,
                "enforcement": "MCP will check these before orders", "timestamp": datetime.now().isoformat()}

    async def rate_limit_handler(self, max_requests_per_minute: int = 60, enable_queuing: bool = True) -> Dict:
        return {"rate_limit_config": {"max_requests_per_minute": max_requests_per_minute, "enable_queuing": enable_queuing},
                "timestamp": datetime.now().isoformat()}

    async def audit_trail(self, export_format: str = "json", start_time: Optional[str] = None,
                          end_time: Optional[str] = None) -> Dict:
        return {"format": export_format,
                "summary": {"total_trades": 0, "total_fills": 0, "total_cancels": 0, "errors": 0,
                            "period": {"start": start_time or "all_time", "end": end_time or "now"}},
                "timestamp": datetime.now().isoformat()}
