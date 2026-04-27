"""Data models for the retail domain - Standalone version without tau2 dependencies."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class Variant(BaseModel):
    """Represents a specific variant of a product with unique options"""

    item_id: str = Field(description="Unique identifier for the item")
    options: Dict[str, str] = Field(description="Options of the item, e.g. color, size")
    available: bool = Field(description="Whether the item is available")
    price: float = Field(description="Price of the item")


class Product(BaseModel):
    """Represents a product type with multiple variants"""

    name: str = Field(description="Name of the product")
    product_id: str = Field(description="Unique identifier for the product")
    variants: Dict[str, Variant] = Field(
        description="Dictionary of variants indexed by item ID"
    )


class UserName(BaseModel):
    """User's full name"""

    first_name: str = Field(description="First name")
    last_name: str = Field(description="Last name")


class UserAddress(BaseModel):
    """User's address details"""

    address1: str = Field(description="First line of the address")
    address2: str = Field(description="Second line of the address")
    city: str = Field(description="City")
    country: str = Field(description="Country")
    state: str = Field(description="State")
    zip: str = Field(description="ZIP code")


class CreditCard(BaseModel):
    """Credit card payment method"""

    source: Literal["credit_card"] = "credit_card"
    id: str = Field(description="Unique identifier for the credit card")
    brand: str = Field(description="Credit card brand")
    last_four: str = Field(description="Last four digits of the credit card")


class PaypalAccount(BaseModel):
    """PayPal payment method"""

    source: Literal["paypal"] = "paypal"
    id: str = Field(description="Unique identifier for the PayPal account")


class GiftCard(BaseModel):
    """Gift card payment method"""

    source: Literal["gift_card"] = "gift_card"
    id: str = Field(description="Unique identifier for the gift card")
    balance: float = Field(description="Balance of the gift card")


PaymentMethod = Union[CreditCard, PaypalAccount, GiftCard]


class User(BaseModel):
    """Represents a customer with their details and orders"""

    user_id: str = Field(description="Unique identifier for the user")
    name: UserName = Field(description="Name of the user")
    address: UserAddress = Field(description="Address of the user")
    email: str = Field(description="Email of the user")
    payment_methods: Dict[str, PaymentMethod] = Field(
        description="Payment methods of the user"
    )
    orders: List[str] = Field(description="Order IDs of the user's orders")


class OrderItem(BaseModel):
    """An item within an order"""

    name: str = Field(description="Name of the item")
    product_id: str = Field(description="Product ID of the item")
    item_id: str = Field(description="Item ID of the item")
    price: float = Field(description="Price of the item")
    options: Dict[str, str] = Field(description="Options of the item")


class OrderPayment(BaseModel):
    """A payment transaction for an order"""

    transaction_type: Literal["payment", "refund"] = Field(
        description="Type of the transaction"
    )
    amount: float = Field(description="Amount of the transaction")
    payment_method_id: str = Field(
        description="Payment method ID of the transaction"
    )


OrderStatus = Literal[
    "pending",
    "pending (item modified)",
    "processed",
    "shipped",
    "delivered",
    "cancelled",
    "return requested",
    "exchange requested",
]


CancelReason = Literal["no longer needed", "ordered by mistake"]


class OrderFullfilment(BaseModel):
    """Fulfillment details for an order"""

    tracking_id: List[str] = Field(description="Tracking IDs of the order")
    item_ids: List[str] = Field(description="Item IDs of the order")


class Order(BaseModel):
    """Represents an order with its items, status, fulfillment and payment details"""

    order_id: str = Field(description="Unique identifier for the order")
    user_id: str = Field(description="Unique identifier for the user")
    address: UserAddress = Field(description="Address of the user")
    items: List[OrderItem] = Field(description="Items in the order")
    status: OrderStatus = Field(description="Status of the order")
    fulfillments: List[OrderFullfilment] = Field(
        description="Fulfillments of the order"
    )
    payment_history: List[OrderPayment] = Field(description="Payments of the order")
    cancel_reason: Optional[CancelReason] = Field(
        description="Reason for cancelling the order",
        default=None,
    )
    exchange_items: Optional[List[str]] = Field(
        description="Items to be exchanged", default=None
    )
    exchange_new_items: Optional[List[str]] = Field(
        description="Items exchanged for", default=None
    )
    exchange_payment_method_id: Optional[str] = Field(
        description="Payment method ID for the exchange", default=None
    )
    exchange_price_difference: Optional[float] = Field(
        description="Price difference for the exchange", default=None
    )
    return_items: Optional[List[str]] = Field(
        description="Items to be returned", default=None
    )
    return_payment_method_id: Optional[str] = Field(
        description="Payment method ID for the return", default=None
    )


class RetailDB(BaseModel):
    """Database containing all retail-related data including products, users and orders"""

    model_config = {"extra": "allow"}

    products: Dict[str, Product] = Field(
        description="Dictionary of all products indexed by product ID"
    )
    users: Dict[str, User] = Field(
        description="Dictionary of all users indexed by user ID"
    )
    orders: Dict[str, Order] = Field(
        description="Dictionary of all orders indexed by order ID"
    )

    _db_path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "RetailDB":
        """Load the database from a JSON file."""
        with open(path, "r") as f:
            data = json.load(f)
        db = cls.model_validate(data)
        db._db_path = str(path)
        return db

    def save(self) -> None:
        """Save the database back to the JSON file."""
        if self._db_path:
            with open(self._db_path, "w") as f:
                json.dump(self.model_dump(exclude={"_db_path"}), f, indent=2)
            print(f"Database saved to {self._db_path}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get the statistics of the database."""
        num_products = len(self.products)
        num_users = len(self.users)
        num_orders = len(self.orders)
        total_num_items = sum(
            len(product.variants) for product in self.products.values()
        )
        return {
            "num_products": num_products,
            "num_users": num_users,
            "num_orders": num_orders,
            "total_num_items": total_num_items,
        }
