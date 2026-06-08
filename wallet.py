"""
Proper EIP-712 signing for Hyperliquid exchange API
Based on official hyperliquid-python SDK signing scheme
"""
import json
import time
from typing import Any, Dict, Optional

from eth_account import Account
from eth_account.messages import encode_typed_data

# ─── type mapping ───────────────────────────────────────────────────────────
TYPE_MAP = {
    str: "string",
    int: "int64",
    bool: "bool",
}


def _sanitize_val(val: Any) -> Any:
    """Convert Python types to Solidity-compatible ones."""
    if isinstance(val, bool):
        return val
    if isinstance(val, float):
        return str(val)
    if isinstance(val, int):
        return val
    return val


def _type_name(key: str) -> str:
    """e.g. 'orders' -> 'Order', 'cancels' -> 'Cancel'."""
    name = key.rstrip("s") if key.endswith("s") else key
    return name[0].upper() + name[1:]


def _build_types(action: Dict[str, Any]) -> Dict[str, list]:
    """
    Recursively build EIP-712 type definitions from the action dict.
    This is how the official Hyperliquid SDK does it.
    """
    seen: Dict[str, list] = {}

    def _walk(name: str, data: Dict[str, Any]):
        if name in seen:
            return
        fields = []
        for k, v in data.items():
            if isinstance(v, dict):
                child = _type_name(k)
                _walk(child, v)
                fields.append({"name": k, "type": child})
            elif isinstance(v, list):
                if v and isinstance(v[0], dict):
                    child = _type_name(k)
                    _walk(child, v[0])
                    fields.append({"name": k, "type": f"{child}[]"})
                else:
                    fields.append({"name": k, "type": "string[]"})
            else:
                t = TYPE_MAP.get(type(v), "string")
                fields.append({"name": k, "type": t})
        seen[name] = fields

    _walk("Action", action)
    return seen


def sign_action(
    action: Dict[str, Any],
    nonce: Optional[int] = None,
    *,
    private_key: str,
    chain_id: int = 42161,  # Arbitrum mainnet; 421614 = testnet
    vault_address: str = "0x0000000000000000000000000000000000000000",
    expiration: int = 0,
) -> Dict[str, Any]:
    """
    EIP-712 sign a Hyperliquid exchange action and return the full
    request payload ready to POST to /exchange.
    """
    if nonce is None:
        nonce = int(time.time() * 1000)

    domain = {
        "name": "HyperliquidSignTransaction",
        "version": "1",
        "chainId": chain_id,
        "verifyingContract": "0x0000000000000000000000000000000000000000",
    }

    types = _build_types(action)

    types["EIP712Domain"] = [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
        {"name": "verifyingContract", "type": "address"},
    ]
    types["HyperliquidTransaction"] = [
        {"name": "action", "type": "Action"},
        {"name": "nonce", "type": "uint64"},
        {"name": "expiration", "type": "uint64"},
        {"name": "vaultAddress", "type": "address"},
    ]

    message = {
        "action": action,
        "nonce": nonce,
        "expiration": expiration,
        "vaultAddress": vault_address,
    }

    typed_data = {
        "domain": domain,
        "types": types,
        "primaryType": "HyperliquidTransaction",
        "message": message,
    }

    signed = Account.sign_message(
        encode_typed_data(full_message=typed_data),
        private_key,
    )

    return {
        "action": action,
        "nonce": nonce,
        "expiration": expiration,
        "signature": signed.signature.hex(),
        "vaultAddress": vault_address,
    }


class WalletManager:
    """Wallet wrapper – derives address from key, signs requests."""

    def __init__(self, private_key: str, account_address: Optional[str] = None):
        if private_key.startswith("0x"):
            private_key = private_key[2:]
        self.private_key = private_key
        self.account = Account.from_key(f"0x{private_key}")
        self.account_address = account_address or self.account.address
        self.vault_address = self.account_address  # can be overridden for API Wallet mode

    async def sign_request(
        self,
        request: Dict[str, Any],
        chain_id: int = 42161,
    ) -> Dict[str, Any]:
        """Sign any Hyperliquid exchange request (action-based)."""
        action = request.get("action", request)
        return sign_action(
            action,
            private_key=f"0x{self.private_key}",
            chain_id=chain_id,
            vault_address=self.vault_address,
        )

    def validate(self) -> bool:
        try:
            return bool(self.account and len(self.private_key) == 64)
        except Exception:
            return False
