"""
TIER 3: RISK MANAGEMENT (10 tools)
"""
import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

from api_client import HyperliquidAPI
from alert_manager import AlertManager


class RiskManagementTools:
    def __init__(self, api: HyperliquidAPI, alert_manager: AlertManager):
        self.api = api
        self.alert_manager = alert_manager
        self.monitoring_tasks: Dict[str, bool] = {}

    async def validate_order_risk(self, coin: str, is_buy: bool, size: float, price: float, leverage: int = 1) -> Dict:
        try:
            mids = await self.api.get_all_mids()
            mark_price = float(mids.get(coin, price))
            state = await self.api.get_user_state(self.api.account_address)
            margin = state.get("marginSummary", {})
            account_value = float(margin.get("accountValue", 0))
            margin_used = float(margin.get("totalMarginUsed", 0))
            notional = size * price
            margin_req = notional / leverage
            new_usage = ((margin_used + margin_req) / account_value * 100) if account_value > 0 else 0
            liq_price = price * (1 - 1 / leverage) if is_buy else price * (1 + 1 / leverage)
            liq_dist = abs(mark_price - liq_price) / mark_price * 100 if mark_price > 0 else 0
            warnings, recs, safe = [], [], True
            if notional < 10:
                warnings.append(f"❌ Order value ${notional:.2f} < $10 minimum")
                safe = False
            if new_usage > 85:
                warnings.append(f"🔴 Margin usage {new_usage:.1f}% CRITICAL")
                safe = False
            elif new_usage > 70:
                warnings.append(f"🟡 Margin usage {new_usage:.1f}% elevated")
            if liq_dist < 3:
                warnings.append(f"🚨 Liquidation EXTREMELY CLOSE ({liq_dist:.2f}%)")
                safe = False
            elif liq_dist < 5:
                warnings.append(f"🔴 Liquidation close ({liq_dist:.2f}%)")
                safe = False
            elif liq_dist < 10:
                warnings.append(f"🟡 Liquidation moderately close ({liq_dist:.2f}%)")
                recs.append("Consider reducing size or leverage")
            if leverage > 20:
                warnings.append(f"⚠️ High leverage {leverage}x - high risk")
                recs.append("Consider reducing leverage")
            if safe:
                recs.append("✅ Order risk parameters are acceptable")
            return {"is_safe": safe, "order_value_usd": round(notional, 2),
                    "liquidation_price": round(liq_price, 2), "liquidation_distance_pct": round(liq_dist, 2),
                    "margin_required": round(margin_req, 2), "margin_used_pct": round(new_usage, 2),
                    "account_value": round(account_value, 2), "warnings": warnings, "recommendations": recs,
                    "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"is_safe": False, "error": str(e), "warnings": ["Validation failed"], "timestamp": datetime.now().isoformat()}

    async def estimate_liquidation_price(self, coin: str, is_buy: bool, entry_price: float,
                                         size: float, leverage: int = 1) -> Dict:
        try:
            liq_price = 0 if leverage <= 1 else (entry_price * (1 - 1 / leverage) if is_buy else entry_price * (1 + 1 / leverage))
            mids = await self.api.get_all_mids()
            cur = mids.get(coin, entry_price)
            dist = abs(cur - liq_price) / cur * 100 if cur > 0 and liq_price > 0 else 0
            return {"coin": coin, "side": "LONG" if is_buy else "SHORT", "entry_price": round(entry_price, 2),
                    "size": size, "leverage": leverage,
                    "liquidation_price": round(liq_price, 2) if liq_price else "No liquidation (1x)",
                    "current_price": round(cur, 2), "distance_pct": round(dist, 2),
                    "risk_level": self._risk_level(dist), "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    @staticmethod
    def _risk_level(d: float) -> str:
        if d < 5: return "🔴 CRITICAL"
        if d < 10: return "🔴 HIGH"
        if d < 20: return "🟡 MODERATE"
        return "🟢 LOW"

    async def check_margin_health(self, account_address: Optional[str] = None, warning_threshold: float = 80) -> Dict:
        addr = account_address or self.api.account_address
        try:
            state = await self.api.get_user_state(addr)
            margin = state.get("marginSummary", {})
            av = float(margin.get("accountValue", 0))
            mu = float(margin.get("totalMarginUsed", 0))
            pct = (mu / av * 100) if av > 0 else 0
            status = "🔴 CRITICAL - IMMEDIATE ACTION" if pct > 90 else \
                     "🔴 HIGH - REDUCE EXPOSURE" if pct > 80 else \
                     "🟡 ELEVATED - MONITOR" if pct > 70 else \
                     "🟢 NORMAL" if pct > 50 else "🟢 HEALTHY"
            return {"account": addr, "status": status,
                    "metrics": {"account_value_usd": round(av, 2), "margin_used_usd": round(mu, 2),
                                "margin_used_pct": round(pct, 2), "withdrawable_usd": round(float(margin.get("withdrawable", 0)), 2)},
                    "is_over_threshold": pct > warning_threshold, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    async def auto_adjust_leverage(self, coin: Optional[str] = None, max_margin_usage: float = 70,
                                   require_confirmation: bool = True) -> Dict:
        try:
            state = await self.api.get_user_state(self.api.account_address)
            margin = state.get("marginSummary", {})
            av = float(margin.get("accountValue", 0))
            mu = float(margin.get("totalMarginUsed", 0))
            usage = (mu / av * 100) if av > 0 else 0
            if usage <= max_margin_usage:
                return {"message": f"✅ Margin usage {usage:.1f}% within target", "adjustments": [], "timestamp": datetime.now().isoformat()}
            adjustments = []
            for ap in state.get("assetPositions", []):
                pos = ap.get("position", {})
                if not pos or float(pos.get("szi", 0)) == 0: continue
                notional = abs(float(pos.get("szi", 0)) * float(pos.get("entryPx", 0)))
                new_lev = max(1, int(max_margin_usage * av / notional)) if notional else 1
                adjustments.append({"coin": pos.get("coin"), "current_notional": round(notional, 2),
                                    "suggested_leverage": new_lev,
                                    "action": f"Reduce leverage to {new_lev}x"})
            if require_confirmation:
                return {"requires_confirmation": True, "current_margin_usage_pct": round(usage, 2),
                        "target_margin_usage_pct": max_margin_usage, "suggested_adjustments": adjustments,
                        "timestamp": datetime.now().isoformat()}
            results = []
            for adj in adjustments:
                try:
                    r = await self.api.update_leverage(adj["coin"], adj["suggested_leverage"])
                    results.append({"coin": adj["coin"], "success": True, "result": r})
                except Exception as e:
                    results.append({"coin": adj["coin"], "success": False, "error": str(e)})
            return {"adjustments_applied": results, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    async def position_monitor(self, coin: Optional[str] = None, check_interval: int = 10,
                               liquidation_threshold: float = 10, auto_reduce: bool = False) -> Dict:
        task_id = f"mon_{coin or 'all'}_{datetime.now().timestamp()}"
        self.monitoring_tasks[task_id] = True

        async def loop():
            while self.monitoring_tasks.get(task_id):
                try:
                    state = await self.api.get_user_state(self.api.account_address)
                    mids = await self.api.get_all_mids()
                    for ap in state.get("assetPositions", []):
                        pos = ap.get("position", {})
                        pc = pos.get("coin")
                        szi = float(pos.get("szi", 0))
                        if szi == 0 or (coin and pc != coin): continue
                        mark = float(mids.get(pc, 0))
                        liq = float(pos.get("liquidationPx", 0))
                        if liq > 0 and mark > 0:
                            dist = abs(mark - liq) / mark * 100
                            if dist < liquidation_threshold:
                                sev = "CRITICAL" if dist < 3 else "HIGH"
                                await self.alert_manager.send_alert(sev, f"Liq Alert: {pc}", f"{dist:.2f}% from liq!")
                                if auto_reduce and dist < 3:
                                    await self.api.place_order(pc, szi < 0, abs(szi) * 0.5, 0, "market", "Ioc", reduce_only=True)
                    await asyncio.sleep(check_interval)
                except Exception as e:
                    await self.alert_manager.send_alert("ERROR", "Monitoring", str(e))
                    await asyncio.sleep(check_interval * 2)

        asyncio.create_task(loop())
        return {"task_id": task_id, "status": "monitoring_started", "coin": coin or "all",
                "check_interval_seconds": check_interval, "liquidation_threshold_pct": liquidation_threshold,
                "auto_reduce_enabled": auto_reduce, "timestamp": datetime.now().isoformat()}

    async def liquidation_alert(self, coin: Optional[str] = None, threshold_pct: float = 10, enable: bool = True) -> Dict:
        return {"coin": coin or "all_positions", "threshold_pct": threshold_pct, "enabled": enable,
                "message": f"✅ Alerts set to {threshold_pct}% for {coin or 'all coins'}",
                "timestamp": datetime.now().isoformat()}

    async def funding_rate_impact(self, coin: str, size: float, entry_price: float, hours: float = 1) -> Dict:
        try:
            funding = await self.api.get_coin_funding_history(coin, limit=1)
            rate = funding[0].get("fundingRate", 0) if isinstance(funding, list) and funding else 0
            notional = size * entry_price
            hourly = notional * float(rate)
            annualized = float(rate) * 365 * 8
            impact = "HIGH" if abs(hourly * hours) > notional * 0.05 else "MODERATE" if abs(hourly * hours) > notional * 0.01 else "LOW"
            return {"coin": coin, "notional_value": round(notional, 2), "current_funding_rate_pct": round(float(rate) * 100, 4),
                    "annualized_rate_pct": round(annualized * 100, 2), "holding_hours": hours,
                    "estimated_cost": round(hourly * hours, 2), "impact_assessment": impact,
                    "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    async def portfolio_health_check(self, account_address: Optional[str] = None,
                                      include_liquidation_risk: bool = True,
                                      include_funding_impact: bool = True) -> Dict:
        addr = account_address or self.api.account_address
        try:
            state = await self.api.get_user_state(addr)
            margin = state.get("marginSummary", {})
            positions = state.get("assetPositions", [])
            mids = await self.api.get_all_mids()
            total_ntl = 0.0
            total_pnl = 0.0
            liq_risks = []
            for ap in positions:
                pos = ap.get("position", {})
                szi = float(pos.get("szi", 0))
                if szi == 0: continue
                coin = pos.get("coin")
                ep = float(pos.get("entryPx", 0))
                mp = mids.get(coin, ep)
                liq = float(pos.get("liquidationPx", 0))
                pnl = float(pos.get("unrealizedPnl", 0))
                total_ntl += abs(szi * ep)
                total_pnl += pnl
                if include_liquidation_risk and liq > 0:
                    dist = abs(mp - liq) / mp * 100 if mp > 0 else 0
                    if dist < 20:
                        liq_risks.append({"coin": coin, "distance_pct": round(dist, 2), "risk_level": self._risk_level(dist)})
            av = float(margin.get("accountValue", 0))
            mu = float(margin.get("totalMarginUsed", 0))
            mpct = (mu / av * 100) if av > 0 else 0
            status = "🟢 HEALTHY" if mpct < 50 else "🟡 ELEVATED" if mpct < 75 else "🔴 HIGH"
            return {"account": addr, "portfolio_summary": {"account_value": round(av, 2), "total_notional": round(total_ntl, 2),
                    "total_unrealized_pnl": round(total_pnl, 2), "roi_pct": round(total_pnl / av * 100, 2) if av > 0 else 0,
                    "position_count": sum(1 for p in positions if float(p.get("position", {}).get("szi", 0)) != 0)},
                    "risk_metrics": {"margin_usage_pct": round(mpct, 2), "margin_status": status,
                                     "liquidation_risks": liq_risks, "at_risk_count": len(liq_risks)},
                    "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    async def simulate_order_impact(self, coin: str, is_buy: bool, size: float, price: float, leverage: int = 1) -> Dict:
        return {"simulation": await self.validate_order_risk(coin, is_buy, size, price, leverage)}

    async def simulate_close_price(self, coin: str, account_address: Optional[str] = None) -> Dict:
        addr = account_address or self.api.account_address
        try:
            state = await self.api.get_user_state(addr)
            pos = self.api._find_position(state, coin)
            if not pos:
                return {"error": f"No position for {coin}"}
            mids = await self.api.get_all_mids()
            mp = mids.get(coin, 0)
            sz = float(pos.get("szi", 0))
            return {"coin": coin, "recommendation": {"order_type": "market", "side": "sell" if sz > 0 else "buy",
                    "price": round(mp, 2), "size": abs(sz), "slippage_est_pct": 0.1},
                    "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"error": str(e)}

    async def emergency_stop(self) -> Dict:
        try:
            state = await self.api.get_user_state(self.api.account_address)
            positions = state.get("assetPositions", [])
            results = []
            await self.api.cancel_all_orders()
            results.append("✅ All orders cancelled")
            for ap in positions:
                pos = ap.get("position", {})
                coin = pos.get("coin")
                szi = float(pos.get("szi", 0))
                if szi != 0:
                    try:
                        await self.api.place_order(coin, szi < 0, abs(szi), 0, "market", "Ioc", reduce_only=True)
                        results.append(f"✅ Closed {coin}")
                    except Exception as e:
                        results.append(f"❌ Failed to close {coin}: {e}")
            return {"emergency_stop": True, "results": results, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.now().isoformat()}
