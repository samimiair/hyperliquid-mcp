"""Core API client for Hyperliquid - powered by official hyperliquid-python-sdk."""
import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

from eth_account.signers.local import LocalAccount
from eth_account import Account
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils.types import Dict as HLDict


def _hl_order_type(order_type: str, tif: str = "Gtc") -> Dict:
    """Convert our order type strings to Hyperliquid SDK OrderType."""
    if order_type == "market":
        return {"market": {}}
    elif order_type == "trigger":
        return {"trigger": {"triggerPx": 0, "isMarket": True, "tpsl": "sl"}}
    else:
        return {"limit": {"tif": tif}}


class HyperliquidAPI:
    """Unified Hyperliquid API — Info + Exchange via official SDK."""

    def __init__(self, private_key: str, account_address: str,
                 vault_address: Optional[str] = None, testnet: bool = False):
        if private_key.startswith("0x"):
            private_key = private_key[2:]
        self.private_key = private_key
        self.account_address = account_address
        self.vault_address = vault_address or account_address
        self.testnet = testnet

        domain = "hyperliquid-testnet.xyz" if testnet else "hyperliquid.xyz"
        self.base_url = f"https://api.{domain}"

        # Create LocalAccount for signing
        self.wallet: LocalAccount = Account.from_key(f"0x{private_key}")

        # Official SDK clients
        self.info = Info(self.base_url, skip_ws=True)
        self.exchange = Exchange(
            wallet=self.wallet,
            base_url=self.base_url,
            vault_address=self.vault_address,
            account_address=self.account_address,
        )

        self._price_cache: Dict[str, float] = {}
        self._cache_time = datetime(2000, 1, 1)

    # ── READ endpoints ────────────────────────────────────────────────

    async def get_all_mids(self) -> Dict[str, float]:
        """Get mid prices (Info.all_mids is sync, so wrap)."""
        now = datetime.now()
        if (now - self._cache_time).total_seconds() < 5 and self._price_cache:
            return self._price_cache
        self._price_cache = self.info.all_mids()
        self._cache_time = now
        return self._price_cache

    async def get_user_state(self, account_address: str, check_spot: bool = False) -> Dict:
        if check_spot:
            return self.info.spot_user_state(account_address)
        return self.info.user_state(account_address)

    async def get_l2_snapshot(self, coin: str) -> Dict:
        result = self.info.l2_snapshot(coin)
        levels = result.get("levels", [[], []])
        return {"coin": coin, "asks": levels[0][:10], "bids": levels[1][:10], "time": result.get("time")}

    async def get_candles_snapshot(self, coin: str, interval: str = "1h",
                                   start_time: Optional[str] = None,
                                   end_time: Optional[str] = None) -> List:
        def _ts(iso): 
            return int(datetime.fromisoformat(iso.replace("Z","+00:00")).timestamp()*1000) if iso else None
        now = int(datetime.now().timestamp() * 1000)
        st = _ts(start_time) or (now - 24*3600*1000)
        et = _ts(end_time) or now
        return self.info.candles_snapshot(coin, interval, st, et)

    # Delegate all info queries to the SDK
    async def get_user_open_orders(self, addr: str) -> List:
        return self.info.open_orders(addr)

    async def get_user_trade_history(self, addr: str) -> List:
        return self.info.user_fills(addr)

    async def get_user_funding_history(self, addr: str, limit: int = 100,
                                       start_time: Optional[str] = None,
                                       end_time: Optional[str] = None) -> List:
        def _ts(iso): 
            return int(datetime.fromisoformat(iso.replace("Z","+00:00")).timestamp()*1000) if iso else None
        now = int(datetime.now().timestamp()*1000)
        return self.info.user_funding_history(addr, _ts(start_time) or (now - 30*24*3600*1000), _ts(end_time) or now)

    async def get_user_fees(self, addr: str) -> Dict:
        return self.info.user_fees(addr)

    async def get_coin_funding_history(self, coin: str, limit: int = 100,
                                       start_time: Optional[str] = None,
                                       end_time: Optional[str] = None) -> List:
        def _ts(iso): 
            return int(datetime.fromisoformat(iso.replace("Z","+00:00")).timestamp()*1000) if iso else None
        now = int(datetime.now().timestamp()*1000)
        return self.info.funding_history(coin, _ts(start_time) or (now - 7*24*3600*1000), _ts(end_time) or now)

    async def get_perp_metadata(self, include_asset_ctxs: bool = False) -> Dict:
        return self.info.meta()

    async def get_spot_metadata(self) -> Dict:
        return self.info.spot_meta()

    async def get_user_staking_summary(self, addr: str) -> Dict:
        return self.info.staking_state(addr)

    async def get_user_sub_accounts(self, addr: str) -> List:
        return self.info.sub_accounts(addr)

    # ── WRITE endpoints (signed via SDK) ───────────────────────────────

    async def place_order(self, coin: str, is_buy: bool, size: float, price: float,
                    order_type: str = "limit", tif: str = "Gtc",
                    reduce_only: bool = False) -> Dict:
        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._place_order_sync(coin, is_buy, size, price, order_type, tif, reduce_only))

    def _place_order_sync(self, coin: str, is_buy: bool, size: float, price: float,
                    order_type: str = "limit", tif: str = "Gtc",
                    reduce_only: bool = False) -> Dict:
        hl_type = _hl_order_type(order_type, tif)
        return self.exchange.order(
            name=coin, is_buy=is_buy, sz=size, limit_px=price,
            order_type=hl_type, reduce_only=reduce_only,
        )

    async def cancel_order(self, coin: str, oid: str) -> Dict:
        return await asyncio.get_event_loop().run_in_executor(
            None, self.exchange.cancel, coin, int(oid))

    async def cancel_all_orders(self, coin: Optional[str] = None) -> Dict:
        if coin:
            return await asyncio.get_event_loop().run_in_executor(
                None, self.exchange.cancel_all, coin)
        return await asyncio.get_event_loop().run_in_executor(
            None, self.exchange.cancel_all)

    async def update_leverage(self, coin: str, leverage: int, is_cross: bool = False) -> Dict:
        return await asyncio.get_event_loop().run_in_executor(
            None, self.exchange.update_leverage, coin, leverage, is_cross)

    async def modify_order(self, coin: str, oid: str, new_price: Optional[float] = None,
                     new_size: Optional[float] = None) -> Dict:
        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.exchange.modify_order(
                int(oid), coin, new_size or 0, new_price or 0))

    async def close_position(self, coin: str, amount: Optional[float] = None) -> Dict:
        return await asyncio.get_event_loop().run_in_executor(
            None, self.exchange.close_position, coin, amount)

    # ── helpers ────────────────────────────────────────────────────────

    async def _coin_to_index(self, coin: str) -> int:
        meta = self.info.meta()
        for i, u in enumerate(meta.get("universe", [])):
            if u["name"].upper() == coin.upper():
                return i
        raise ValueError(f"Unknown coin: {coin}")

    def _find_position(self, user_state: Dict, coin: str) -> Optional[Dict]:
        for ap in user_state.get("assetPositions", []):
            pos = ap.get("position", {})
            if pos.get("coin") == coin:
                return pos
        return None

    async def close(self):
        """No-op — SDK manages its own sessions."""
        pass
