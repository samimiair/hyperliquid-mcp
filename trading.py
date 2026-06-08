"""
TIER 2: TRADING EXECUTION (12 tools)
"""
from typing import Any, Dict, Optional
from datetime import datetime
import asyncio

from api_client import HyperliquidAPI


class TradingTools:
    def __init__(self, api: HyperliquidAPI):
        self.api = api

    async def place_order(self, coin: str, is_buy: bool, size: float, price: float,
                          leverage: int = 1, order_type: str = "limit",
                          tif: str = "Ioc", reduce_only: bool = False) -> Dict:
        if size <= 0:
            return {"error": "Size must be > 0"}
        if price < 0:
            return {"error": "Price cannot be negative"}
        if not 1 <= leverage <= 50:
            return {"error": "Leverage must be 1-50"}
        try:
            result = await self.api.place_order(coin, is_buy, size, price, order_type, tif, reduce_only, leverage)
            return {"success": True, "coin": coin, "side": "BUY" if is_buy else "SELL", "size": size,
                    "price": price, "leverage": leverage, "order_type": order_type, "result": result,
                    "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"success": False, "error": str(e), "timestamp": datetime.now().isoformat()}

    async def place_bracket_order(self, coin: str, is_buy: bool, entry_price: float,
                                  size: float, take_profit: float, stop_loss: float,
                                  leverage: int = 1) -> Dict:
        if is_buy and not (stop_loss < entry_price < take_profit):
            return {"error": "Invalid prices for long: SL < Entry < TP"}
        if not is_buy and not (take_profit < entry_price < stop_loss):
            return {"error": "Invalid prices for short: TP < Entry < SL"}
        try:
            entry = await self.place_order(coin, is_buy, size, entry_price, leverage, "limit", "Gtc")
            if not entry.get("success"):
                return entry
            tp = await self.place_order(coin, not is_buy, size, take_profit, 1, "limit", "Gtc", reduce_only=True)
            sl = await self.place_order(coin, not is_buy, size, stop_loss, 1, "limit", "Gtc", reduce_only=True)
            return {"success": True, "bracket": {"entry": entry.get("result"), "take_profit": tp.get("result"), "stop_loss": sl.get("result")},
                    "summary": {"coin": coin, "side": "LONG" if is_buy else "SHORT", "size": size,
                                "entry_price": entry_price, "take_profit": take_profit, "stop_loss": stop_loss},
                    "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"success": False, "error": str(e), "timestamp": datetime.now().isoformat()}

    async def modify_order(self, coin: str, oid: str, new_price: Optional[float] = None,
                           new_size: Optional[float] = None) -> Dict:
        try:
            result = await self.api.modify_order(coin, oid, new_price, new_size)
            return {"success": True, "coin": coin, "oid": oid, "new_price": new_price, "new_size": new_size,
                    "result": result, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"success": False, "error": str(e), "timestamp": datetime.now().isoformat()}

    async def cancel_order(self, coin: str, oid: str) -> Dict:
        try:
            result = await self.api.cancel_order(coin, oid)
            return {"success": True, "coin": coin, "oid": oid, "result": result, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"success": False, "error": str(e), "timestamp": datetime.now().isoformat()}

    async def cancel_all_orders(self, coin: Optional[str] = None) -> Dict:
        try:
            result = await self.api.cancel_all_orders(coin)
            return {"success": True, "coin": coin or "all", "result": result, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"success": False, "error": str(e), "timestamp": datetime.now().isoformat()}

    async def get_position_by_coin(self, coin: str, account_address: Optional[str] = None) -> Dict:
        addr = account_address or self.api.wallet.account_address
        try:
            state = await self.api.get_user_state(addr)
            pos = self.api._find_position(state, coin)
            if not pos:
                return {"coin": coin, "position": None, "message": f"No position for {coin}"}
            return {"coin": coin, "position": pos, "size": float(pos.get("szi", 0)),
                    "entry_price": float(pos.get("entryPx", 0)), "mark_price": float(pos.get("markPx", 0)),
                    "liquidation_price": float(pos.get("liquidationPx", 0)),
                    "unrealized_pnl": float(pos.get("unrealizedPnl", 0)),
                    "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    async def close_position(self, coin: str, amount_to_close: Optional[float] = None) -> Dict:
        try:
            state = await self.api.get_user_state(self.api.wallet.account_address)
            pos = self.api._find_position(state, coin)
            if not pos:
                return {"error": f"No position for {coin}"}
            cur_size = float(pos.get("szi", 0))
            if cur_size == 0:
                return {"error": f"No open position for {coin}", "timestamp": datetime.now().isoformat()}
            close_size = abs(amount_to_close or cur_size)
            is_buy = cur_size < 0
            mids = await self.api.get_all_mids()
            price = mids.get(coin, 0)
            result = await self.place_order(coin, is_buy, close_size, 0, 1, "market", "Ioc", reduce_only=True)
            return {"success": True, "coin": coin, "closed_size": close_size, "price": price,
                    "result": result, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"success": False, "error": str(e), "timestamp": datetime.now().isoformat()}

    async def update_leverage(self, coin: str, leverage: int, is_cross: bool = False) -> Dict:
        try:
            if not 1 <= leverage <= 50:
                return {"error": "Leverage must be 1-50"}
            result = await self.api.update_leverage(coin, leverage, is_cross)
            return {"success": True, "coin": coin, "leverage": leverage, "margin_type": "cross" if is_cross else "isolated",
                    "result": result, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"success": False, "error": str(e), "timestamp": datetime.now().isoformat()}

    async def get_funding_history(self, account_address: Optional[str] = None, start_time: Optional[str] = None,
                                  end_time: Optional[str] = None, limit: int = 100) -> Dict:
        addr = account_address or self.api.wallet.account_address
        try:
            funding = await self.api.get_user_funding_history(addr, limit, start_time, end_time)
            total = sum(float(f.get("funding", 0)) for f in funding) if isinstance(funding, list) else 0
            return {"account": addr, "total_paid": total, "record_count": len(funding) if isinstance(funding, list) else 0,
                    "funding_history": funding, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    async def calculate_funding_impact(self, coin: str, size: float, days: float = 1) -> Dict:
        try:
            funding = await self.api.get_coin_funding_history(coin, limit=1)
            rate = funding[0].get("fundingRate", 0) if isinstance(funding, list) and funding else 0
            mids = await self.api.get_all_mids()
            price = mids.get(coin, 0)
            notional = size * price
            daily_rate = float(rate) * 8  # 3 funding periods/day
            total = notional * daily_rate * days
            return {"coin": coin, "position_size": size, "position_price": price, "notional_value": notional,
                    "current_funding_rate": float(rate), "daily_rate_pct": round(daily_rate * 100, 4),
                    "estimated_cost": round(total, 2), "days": days, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.now().isoformat()}
