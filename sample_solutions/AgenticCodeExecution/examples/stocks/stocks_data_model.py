"""Data models for the stocks domain."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]
OrderStatus = Literal["open", "filled", "cancelled"]


class Position(BaseModel):
    """Current holdings for a stock symbol."""

    quantity: int = Field(description="Number of shares held")
    avg_cost: float = Field(description="Average cost basis per share")


class Account(BaseModel):
    """Trading account profile and portfolio snapshot."""

    account_id: str = Field(description="Unique account identifier")
    name: str = Field(description="Account holder name")
    email: str = Field(description="Account holder email")
    cash_balance: float = Field(description="Available cash balance")
    positions: Dict[str, Position] = Field(
        description="Positions keyed by stock symbol"
    )
    watchlist: list[str] = Field(description="Saved watchlist symbols")
    order_ids: list[str] = Field(description="Order IDs associated with this account")


class Quote(BaseModel):
    """Current market quote for a tradable symbol."""

    symbol: str = Field(description="Ticker symbol")
    name: str = Field(description="Company name")
    sector: str = Field(description="Market sector")
    current_price: float = Field(description="Latest traded price")
    day_open: float = Field(description="Opening price for the day")
    day_high: float = Field(description="Highest price for the day")
    day_low: float = Field(description="Lowest price for the day")
    volume: int = Field(description="Trading volume for the day")


class Order(BaseModel):
    """Trade order record."""

    order_id: str = Field(description="Unique order identifier")
    account_id: str = Field(description="Account that placed the order")
    symbol: str = Field(description="Ticker symbol")
    side: OrderSide = Field(description="Buy or sell direction")
    order_type: OrderType = Field(description="Order execution type")
    quantity: int = Field(description="Number of shares")
    limit_price: Optional[float] = Field(
        default=None,
        description="Limit price for limit orders",
    )
    status: OrderStatus = Field(description="Current order status")
    executed_price: Optional[float] = Field(
        default=None,
        description="Execution price when filled",
    )
    created_at: str = Field(description="Order creation timestamp in ISO format")
    filled_at: Optional[str] = Field(
        default=None,
        description="Fill timestamp in ISO format",
    )


class StocksDB(BaseModel):
    """Database containing stocks accounts, quotes, and orders."""

    model_config = {"extra": "allow"}

    accounts: Dict[str, Account] = Field(
        description="Dictionary of accounts indexed by account_id"
    )
    market: Dict[str, Quote] = Field(
        description="Dictionary of quotes indexed by ticker symbol"
    )
    orders: Dict[str, Order] = Field(
        description="Dictionary of orders indexed by order_id"
    )
    meta: Dict[str, Any] = Field(default_factory=dict, description="Metadata section")

    _db_path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "StocksDB":
        """Load the database from a JSON file."""
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        db = cls.model_validate(data)
        db._db_path = str(path)
        return db

    def save(self) -> None:
        """Save the database back to the JSON file."""
        if self._db_path:
            with open(self._db_path, "w", encoding="utf-8") as handle:
                json.dump(self.model_dump(exclude={"_db_path"}, mode="json"), handle, indent=2)

    def get_statistics(self) -> Dict[str, Any]:
        """Get high-level statistics for the stocks database."""
        return {
            "num_accounts": len(self.accounts),
            "num_symbols": len(self.market),
            "num_orders": len(self.orders),
        }
