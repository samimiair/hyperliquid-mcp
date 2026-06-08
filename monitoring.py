"""
TIER 1: MONITORING & ANALYTICS (14+6 tools)
"""
from typing import Any, Dict, List, Optional
from datetime import datetime

from api_client import HyperliquidAPI


class MonitoringTools:
    def __init__(self, api: HyperliquidAPI):
        self.api = api

    async def get_user_state(self, account_address: Optional[str] = None, check_spot: bool = False) -> Dict:
        addr = account_address or self.api.wallet.account_address
        state = await self.api.get_user_state(addr, check_spot)
        return {
            "account": addr,
            "positions": state.get("assetPositions", []),
            "margin": state.get("marginSummary", {}),
            "withdrawable": state.get("withdrawable", 0),
            "timestamp": datetime.now().isoformat(),
        }

    async def get_user_open_orders(self, account_address: Optional[str] = None) -> Dict:
        addr = account_address or self.api.wallet.account_address
        orders = await self.api.get_user_open_orders(addr)
        return {"account": addr, "open_orders_count": len(orders) if isinstance(orders, list) else 0, "orders": orders, "timestamp": datetime.now().isoformat()}

    async def get_user_trade_history(self, account_address: Optional[str] = None, limit: int = 100) -> Dict:
        addr = account_address or self.api.wallet.account_address
        trades = await self.api.get_user_trade_history(addr, limit)
        return {"account": addr, "total_trades": len(trades) if isinstance(trades, list) else 0, "limit": limit, "trades": trades, "timestamp": datetime.now().isoformat()}

    async def get_user_funding_history(self, account_address: Optional[str] = None, start_time: Optional[str] = None, end_time: Optional[str] = None, limit: int = 100) -> Dict:
        addr = account_address or self.api.wallet.account_address
        funding = await self.api.get_user_funding_history(addr, limit, start_time, end_time)
        total = sum(float(f.get("funding", 0)) for f in funding) if isinstance(funding, list) else 0
        return {"account": addr, "total_funding_paid": total, "record_count": len(funding) if isinstance(funding, list) else 0, "funding_history": funding, "timestamp": datetime.now().isoformat()}

    async def get_user_fees(self, account_address: Optional[str] = None) -> Dict:
        addr = account_address or self.api.wallet.account_address
        fees = await self.api.get_user_fees(addr)
        return {"account": addr, "fee_structure": fees, "timestamp": datetime.now().isoformat()}

    async def get_user_staking_summary(self, account_address: Optional[str] = None) -> Dict:
        addr = account_address or self.api.wallet.account_address
        staking = await self.api.get_user_staking_summary(addr)
        return {"account": addr, "staking_info": staking, "timestamp": datetime.now().isoformat()}

    async def get_user_order_by_oid(self, account_address: str, oid: str) -> Dict:
        orders = await self.api.get_user_open_orders(account_address)
        for o in orders if isinstance(orders, list) else []:
            if str(o.get("oid", "")) == str(oid):
                return {"account": account_address, "order": o, "timestamp": datetime.now().isoformat()}
        return {"account": account_address, "error": f"Order {oid} not found", "timestamp": datetime.now().isoformat()}

    async def get_user_sub_accounts(self, account_address: Optional[str] = None) -> Dict:
        addr = account_address or self.api.wallet.account_address
        subs = await self.api.get_user_sub_accounts(addr)
        lst = subs if isinstance(subs, list) else []
        return {"main_account": addr, "sub_accounts": lst, "count": len(lst), "timestamp": datetime.now().isoformat()}

    async def get_all_mids(self) -> Dict:
        mids = await self.api.get_all_mids()
        return {"prices": mids, "pair_count": len(mids), "timestamp": datetime.now().isoformat()}

    async def get_l2_snapshot(self, coin: str) -> Dict:
        snap = await self.api.get_l2_snapshot(coin)
        return {"coin": coin, "bids": snap.get("bids", [])[:5], "asks": snap.get("asks", [])[:5], "timestamp": datetime.now().isoformat()}

    async def get_candles_snapshot(self, coin: str, interval: str = "1h", start_time: Optional[str] = None, end_time: Optional[str] = None) -> Dict:
        candles = await self.api.get_candles_snapshot(coin, interval, start_time, end_time)
        return {"coin": coin, "interval": interval, "candle_count": len(candles) if isinstance(candles, list) else 0, "candles": candles, "timestamp": datetime.now().isoformat()}

    async def get_coin_funding_history(self, coin: str, start_time: Optional[str] = None, end_time: Optional[str] = None, limit: int = 100) -> Dict:
        funding = await self.api.get_coin_funding_history(coin, limit, start_time, end_time)
        rates = [float(f.get("fundingRate", 0)) for f in funding] if isinstance(funding, list) else []
        avg = sum(rates) / len(rates) if rates else 0
        return {"coin": coin, "record_count": len(rates), "average_funding_rate": avg, "funding_history": funding, "timestamp": datetime.now().isoformat()}

    async def get_perp_metadata(self, include_asset_ctxs: bool = False) -> Dict:
        meta = await self.api.get_perp_metadata(include_asset_ctxs)
        pairs = [{"name": p.get("name"), "max_leverage": p.get("maxLeverage")} for p in meta.get("universe", [])[:10]]
        return {"market_type": "perpetuals", "pair_count": len(meta.get("universe", [])), "pairs": pairs, "timestamp": datetime.now().isoformat()}

    async def get_spot_metadata(self, include_asset_ctxs: bool = False) -> Dict:
        meta = await self.api.get_spot_metadata()
        tokens = [t.get("name") for t in meta.get("tokens", [])[:10]]
        return {"market_type": "spot", "token_count": len(meta.get("tokens", [])), "tokens": tokens, "timestamp": datetime.now().isoformat()}

    # ── Bonus analytics ────────────────────────────────────────────────

    async def analyze_positions(self, account_address: Optional[str] = None, detailed: bool = True) -> Dict:
        addr = account_address or self.api.wallet.account_address
        state = await self.get_user_state(addr)
        orders = await self.get_user_open_orders(addr)
        trades = await self.get_user_trade_history(addr, limit=50)
        funding = await self.get_user_funding_history(addr, limit=30)

        positions = state.get("positions", [])
        total_notional = 0.0
        total_pnl = 0.0
        at_risk = []
        for ap in positions:
            pos = ap.get("position", {})
            if not pos:
                continue
            szi = float(pos.get("szi", 0))
            if szi == 0:
                continue
            entry_px = float(pos.get("entryPx", 0))
            pnl = float(pos.get("unrealizedPnl", 0))
            notional = abs(szi * entry_px)
            total_notional += notional
            total_pnl += pnl
            liq_px = float(pos.get("liquidationPx", 0))
            mark_px = float(pos.get("markPx", 0))
            if mark_px > 0 and liq_px > 0:
                dist = abs(mark_px - liq_px) / mark_px * 100
                if dist < 15:
                    at_risk.append({"coin": pos.get("coin"), "distance_pct": dist, "pnl": pnl})
        return {
            "account": addr,
            "summary": {"total_notional": total_notional, "total_unrealized_pnl": total_pnl,
                        "positions_count": sum(1 for p in positions if float(p.get("position", {}).get("szi", 0)) != 0),
                        "at_risk_count": len(at_risk), "total_funding_paid": funding.get("total_funding_paid", 0)},
            "at_risk_positions": at_risk,
            "recommendations": self._gen_recs(state, at_risk, total_pnl),
            "timestamp": datetime.now().isoformat(),
        }

    def _gen_recs(self, state: Dict, at_risk: List, pnl: float) -> List[str]:
        recs = []
        if at_risk:
            recs.append("⚠️ Reduce leverage or close risky positions")
        margin = state.get("margin", {})
        if margin:
            usage = (float(margin.get("totalMarginUsed", 0)) / float(margin.get("accountValue", 1))) * 100
            if usage > 80:
                recs.append("🔴 High margin usage - close some positions")
            elif usage > 60:
                recs.append("🟡 Moderate margin usage - be cautious")
        if pnl > 0:
            recs.append("✅ Positive P&L - consider taking profits")
        return recs or ["✨ Portfolio looks healthy"]

    async def performance_metrics(self, account_address: Optional[str] = None, start_time: Optional[str] = None, end_time: Optional[str] = None) -> Dict:
        addr = account_address or self.api.wallet.account_address
        trades = await self.get_user_trade_history(addr, limit=1000)
        trade_list = trades.get("trades", [])
        winning = sum(1 for t in trade_list if float(t.get("closedPnl", 0)) > 0)
        losing = sum(1 for t in trade_list if float(t.get("closedPnl", 0)) < 0)
        total = winning + losing
        total_pnl = sum(float(t.get("closedPnl", 0)) for t in trade_list)
        return {"account": addr, "metrics": {"total_trades": total, "winning_trades": winning, "losing_trades": losing,
                                              "win_rate_pct": round(winning / total * 100, 2) if total else 0,
                                              "total_pnl": total_pnl, "avg_trade_pnl": round(total_pnl / total, 2) if total else 0},
                "timestamp": datetime.now().isoformat()}

    async def coin_comparison(self, coins: List[str], metrics: str = "funding") -> Dict:
        mids = await self.get_all_mids()
        comparison = []
        for coin in coins:
            price = mids.get(coin, 0)
            funding = await self.get_coin_funding_history(coin, limit=1)
            rate = funding.get("average_funding_rate", 0)
            comparison.append({"coin": coin, "price": price, "funding_rate": round(rate * 100, 4)})
        return {"coins": coins, "metric": metrics, "comparison": comparison, "timestamp": datetime.now().isoformat()}

    async def backtest_strategy(self, coin: str, strategy: str, start_time: str, end_time: str, interval: str = "1h") -> Dict:
        candles = await self.get_candles_snapshot(coin, interval, start_time, end_time)
        candle_list = candles.get("candles", [])
        if not candle_list:
            return {"error": "No candle data available"}
        results = {}
        if strategy == "moving_average":
            results = self._bt_ma(candle_list)
        elif strategy == "rsi":
            results = self._bt_rsi(candle_list)
        elif strategy == "momentum":
            results = self._bt_momentum(candle_list)
        return {"coin": coin, "strategy": strategy, "candles_analyzed": len(candle_list), "backtest_results": results, "timestamp": datetime.now().isoformat()}

    @staticmethod
    def _bt_ma(candles: List[Dict]) -> Dict:
        closes = [float(c.get("c", 0)) for c in candles]
        if len(closes) < 20:
            return {"error": "Not enough candles"}
        ma = sum(closes[-20:]) / 20
        cur = closes[-1]
        return {"signal": "BUY" if cur > ma else "SELL", "ma20": round(ma, 2), "current_price": round(cur, 2), "distance_pct": round((cur - ma) / ma * 100, 2)}

    @staticmethod
    def _bt_rsi(candles: List[Dict]) -> Dict:
        closes = [float(c.get("c", 0)) for c in candles]
        if len(closes) < 14:
            return {"error": "Not enough candles"}
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas[-14:]]
        losses = [-d if d < 0 else 0 for d in deltas[-14:]]
        avg_g = sum(gains) / 14
        avg_l = sum(losses) / 14
        rs = avg_g / avg_l if avg_l else 0
        rsi = 100 - 100 / (1 + rs)
        signal = "OVERBOUGHT" if rsi > 70 else ("OVERSOLD" if rsi < 30 else "NEUTRAL")
        return {"signal": signal, "rsi": round(rsi, 2)}

    @staticmethod
    def _bt_momentum(candles: List[Dict]) -> Dict:
        closes = [float(c.get("c", 0)) for c in candles]
        if len(closes) < 5:
            return {"error": "Not enough candles"}
        mom = closes[-1] - closes[-5]
        pct = mom / closes[-5] * 100 if closes[-5] else 0
        return {"signal": "BULLISH" if mom > 0 else "BEARISH", "momentum": round(mom, 2), "momentum_pct": round(pct, 2)}

    async def get_market_sentiment(self, coin: Optional[str] = None, timeframe: str = "1d") -> Dict:
        if coin:
            funding = await self.get_coin_funding_history(coin, limit=24)
            mids = await self.get_all_mids()
            price = mids.get(coin, 0)
            return {"coin": coin, "sentiment": {"current_price": price, "average_funding": round(funding.get("average_funding_rate", 0) * 100, 4), "timeframe": timeframe}}
        return {"market_sentiment": "Data aggregation coming soon"}

    async def optimize_portfolio(self, account_address: Optional[str] = None, strategy: str = "balanced") -> Dict:
        addr = account_address or self.api.wallet.account_address
        recs = {"conservative": ["Reduce leverage to 1-2x", "Limit positions to 2-3 coins"],
                "balanced": ["Target leverage 3-5x", "4-5 positions", "Diversify coins"],
                "aggressive": ["Can use 10x leverage", "5+ positions", "Active rebalancing"]}
        return {"account": addr, "strategy": strategy, "recommendations": recs.get(strategy, []), "timestamp": datetime.now().isoformat()}
