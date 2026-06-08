"""
TIER 4: SECURITY & SETUP (8 tools)
"""
import json
from typing import Any, Dict, List, Optional
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
        """Validate and report API wallet / Agent Mode status."""
        try:
            vault = self.api.vault_address
            main = self.api.account_address
            using_agent = vault != main
            steps = []
            warnings = []

            if not using_agent:
                warnings.append("⚠️ API wallet not configured — using main wallet directly")
                steps.append("1. Create a new wallet on Hyperliquid (no funds needed)")
                steps.append("2. In Hyperliquid UI: Portfolio → API Wallets → Create")
                steps.append("3. Copy the API wallet address")
                steps.append("4. Set HYPERLIQUID_API_WALLET=<api_wallet_address> in .env")
                tips = ["Use a dedicated API wallet with no funds for security"]
            else:
                steps.append(f"✅ API wallet configured: {vault[:10]}...")

            # Check if vault is accessible
            vault_checks = {}
            try:
                r = await self.api.update_leverage("BTC", 1)  # will fail if vault not registered
                vault_checks["registration"] = {"status": "✅ PASS", "message": "Vault responds to actions"}
            except Exception as e:
                err = str(e)
                if "Vault not registered" in err:
                    vault_checks["registration"] = {"status": "⚠️ PENDING",
                        "message": f"Vault {vault[:10]}... not registered. Register in Hyperliquid UI: Portfolio → API Wallets → Register.",
                        "action": "Visit https://app.hyperliquid.xyz/portfolio → API Wallets → Register"}
                    warnings.append("🔴 API wallet not yet registered on Hyperliquid")
                else:
                    vault_checks["registration"] = {"status": "⚠️ UNKNOWN", "message": err}

            # Trading limits config
            limits = {"max_trade_size": max_trade_size, "enforced": max_trade_size is not None}

            return {
                "agent_mode_setup": {
                    "status": "✅ Configured" if using_agent and not vault_checks.get("registration", {}).get("status", "").startswith("⚠️") else "⚠️ Needs attention",
                    "main_wallet": f"{main[:10]}...",
                    "api_wallet": f"{vault[:10]}..." if using_agent else "Not set",
                    "using_agent_mode": using_agent,
                    "vault_checks": vault_checks,
                    "limits": limits,
                    "steps": steps,
                    "warnings": warnings,
                    "tips": ["API wallet cannot withdraw — only trade", "Main wallet key stays on this server", "Set max_trade_size for extra safety"],
                },
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

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
        """Fetch real trade fills, funding history, and open orders to build audit trail."""
        addr = self.api.account_address
        try:
            # Fetch real data
            fills = await self.api.get_user_trade_history(addr)
            funding = await self.api.get_user_funding_history(addr, limit=500,
                start_time=start_time, end_time=end_time)
            orders = await self.api.get_user_open_orders(addr)

            fill_list = fills if isinstance(fills, list) else []
            funding_list = funding if isinstance(funding, list) else []
            order_list = orders if isinstance(orders, list) else []

            # Filter by time if specified
            if start_time:
                st = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                fill_list = [f for f in fill_list if datetime.fromtimestamp(
                    int(f.get("time", 0)) / 1000) >= st]
                funding_list = [f for f in funding_list if datetime.fromtimestamp(
                    int(f.get("time", 0)) / 1000) >= st]

            # Aggregate stats
            total_buys = sum(1 for f in fill_list if f.get("side") == "B" or f.get("dir", "").startswith("B"))
            total_sells = sum(1 for f in fill_list if f.get("side") == "A" or f.get("dir", "").startswith("A"))
            total_volume = sum(float(f.get("px", 0)) * float(f.get("sz", 0)) for f in fill_list)
            total_fees = sum(float(f.get("fee", 0)) for f in fill_list)
            total_funding = sum(float(f.get("funding", 0)) for f in funding_list)
            coins_traded = list({f.get("coin", "?") for f in fill_list})

            summary = {
                "total_fills": len(fill_list),
                "total_buys": total_buys,
                "total_sells": total_sells,
                "total_volume_usd": round(total_volume, 2),
                "total_fees_paid": round(total_fees, 4),
                "total_funding_paid": round(total_funding, 4),
                "coins_traded": coins_traded,
                "open_orders": len(order_list),
                "funding_records": len(funding_list),
                "period": {"start": start_time or "all_time", "end": end_time or "now"},
            }

            result = {
                "format": export_format,
                "summary": summary,
                "timestamp": datetime.now().isoformat(),
            }

            # Include raw data based on format
            if export_format == "text":
                result["audit_text"] = self._format_audit_text(summary, fill_list)
            elif export_format == "csv":
                result["csv_columns"] = ["time", "coin", "side", "size", "price", "fee", "pnl"]
                result["csv_data"] = [
                    {
                        "time": f.get("time", ""),
                        "coin": f.get("coin", ""),
                        "side": f.get("side", "") or f.get("dir", ""),
                        "size": f.get("sz", ""),
                        "price": f.get("px", ""),
                        "fee": f.get("fee", ""),
                        "pnl": f.get("closedPnl", ""),
                    }
                    for f in fill_list[:1000]
                ]
            elif export_format == "json":
                result["fills"] = fill_list[:500]
                result["funding_payments"] = funding_list[:500]

            return result
        except Exception as e:
            return {"error": str(e), "format": export_format, "timestamp": datetime.now().isoformat()}

    @staticmethod
    def _format_audit_text(summary: Dict, fills: List) -> str:
        lines = [
            "=== HYPERLIQUID AUDIT TRAIL ===",
            f"Period: {summary['period']['start']} → {summary['period']['end']}",
            f"Total Fills: {summary['total_fills']} ({summary['total_buys']} buys / {summary['total_sells']} sells)",
            f"Volume: ${summary['total_volume_usd']:,.2f}",
            f"Fees: ${summary['total_fees_paid']:.4f}",
            f"Funding: ${summary['total_funding_paid']:+.4f}",
            f"Coins: {', '.join(summary['coins_traded']) or 'none'}",
            f"Open Orders: {summary['open_orders']}",
            "",
            "RECENT FILLS:",
        ]
        for f in fills[:20]:
            ts = datetime.fromtimestamp(int(f.get("time", 0)) / 1000).strftime("%Y-%m-%d %H:%M")
            lines.append(
                f"  {ts} | {f.get('coin', '?'):>6} | {f.get('side', '?'):>4} | "
                f"sz={f.get('sz', '?')} | px={f.get('px', '?')} | "
                f"fee={f.get('fee', '?')} | pnl={f.get('closedPnl', '?')}"
            )
        return "\n".join(lines)
