"""Input validation for Hyperliquid trading parameters."""


class InputValidator:
    """Validate user inputs for trading operations."""

    @staticmethod
    def validate_coin(coin: str) -> bool:
        return bool(coin and coin.isalpha())

    @staticmethod
    def validate_size(size: float) -> bool:
        return size > 0

    @staticmethod
    def validate_price(price: float) -> bool:
        return price >= 0

    @staticmethod
    def validate_leverage(leverage: int) -> bool:
        return 1 <= leverage <= 50

    @staticmethod
    def validate_address(address: str) -> bool:
        return address.startswith("0x") and len(address) == 42
