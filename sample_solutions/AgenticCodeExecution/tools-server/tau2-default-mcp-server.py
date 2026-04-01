#!/usr/bin/env python3
"""
MCP Server for Retail Tools - tau2 default parity
"""

import argparse
import inspect
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from fastmcp import FastMCP

from retail_data_model import (
    GiftCard,
    Order,
    OrderPayment,
    PaymentMethod,
    Product,
    RetailDB,
    User,
    UserAddress,
    Variant,
)


DEFAULT_DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "retail" / "db.json")

mcp = FastMCP(
    "Retail Tools Server",
    instructions="""You are a retail customer service agent. Use these tools to help customers with:
- Finding their user ID by email or name+zip
- Looking up order details and status
- Cancelling pending orders
- Modifying pending orders (items, address, payment)
- Processing returns for delivered orders
- Processing exchanges for delivered orders
- Looking up product information

Always verify the user's identity before making changes. Ask for confirmation before
modifying orders or processing returns/exchanges.""",
)


_db: Optional[RetailDB] = None
_original_db_path: str = ""
_session_dbs: Dict[str, RetailDB] = {}
SESSION_DB_DIR = Path(__file__).parent / "session_dbs"
SESSION_DB_DIR.mkdir(exist_ok=True)


def get_db(session_id: str = "") -> RetailDB:
    global _db, _original_db_path

    if _db is None:
        db_path = os.environ.get("RETAIL_DB_PATH", DEFAULT_DB_PATH)
        _original_db_path = db_path
        _db = RetailDB.load(db_path)
        _db._db_path = ""
        print(f"Loaded template database from {db_path}")
        print(f"  - {len(_db.products)} products")
        print(f"  - {len(_db.users)} users")
        print(f"  - {len(_db.orders)} orders")

    if not session_id:
        return _db

    if session_id not in _session_dbs:
        db = RetailDB.load(_original_db_path)
        session_db_file = SESSION_DB_DIR / f"{session_id[:32]}.json"
        db._db_path = str(session_db_file)
        _session_dbs[session_id] = db
        print(
            f"🆕 Created pristine DB for session {session_id[:8]}... "
            f"({len(_session_dbs)} active sessions)"
        )

    return _session_dbs[session_id]


class RetailTools:
    """All the tools for the retail domain."""

    db: RetailDB

    def __init__(self, db: RetailDB) -> None:
        self.db = db

    def _get_order(self, order_id: str) -> Order:
        """Get the order from the database.

        Args:
            order_id: The order id, such as '#W0000000'. Be careful there is a '#' symbol at the beginning of the order id.

        Returns:
            The order.

        Raises:
            ValueError: If the order is not found.
        """
        if order_id not in self.db.orders:
            raise ValueError("Order not found")
        return self.db.orders[order_id]

    def _get_user(self, user_id: str) -> User:
        """Get the user from the database.

        Args:
            user_id: The user id, such as 'sara_doe_496'.

        Returns:
            The user.

        Raises:
            ValueError: If the user is not found.
        """
        if user_id not in self.db.users:
            raise ValueError("User not found")
        return self.db.users[user_id]

    def _get_product(self, product_id: str) -> Product:
        """Get the product from the database.

        Args:
            product_id: The product id, such as '6086499569'. Be careful the product id is different from the item id.

        Returns:
            The product.

        Raises:
            ValueError: If the product is not found.
        """
        if product_id not in self.db.products:
            raise ValueError("Product not found")
        return self.db.products[product_id]

    def _get_variant(self, product_id: str, variant_id: str) -> Variant:
        """Get the variant from the database.

        Args:
            product_id: The product id, such as '6086499569'. Be careful the product id is different from the item id.
            variant_id: The variant id, such as '1008292230'.

        Returns:
            The variant.

        Raises:
            ValueError: If the variant is not found.
        """
        product = self._get_product(product_id)
        if variant_id not in product.variants:
            raise ValueError("Variant not found")
        return product.variants[variant_id]

    def _get_payment_method(
        self, user_id: str, payment_method_id: str
    ) -> PaymentMethod:
        """Get the payment method from the database.

        Args:
            payment_method_id: The payment method id, such as 'gift_card_0000000' or 'credit_card_0000000'.

        Returns:
            The payment method.

        Raises:
            ValueError: If the payment method is not found.
        """
        user = self._get_user(user_id)
        if payment_method_id not in user.payment_methods:
            raise ValueError("Payment method not found")
        return user.payment_methods[payment_method_id]

    def _is_pending_order(self, order: Order) -> bool:
        """Check if the order is pending. This is not a strict check, and not meant to be used for modify_items in pending orders.

        Args:
            order: The order.
        """
        return "pending" in order.status

    def calculate(self, expression: str) -> str:
        """
        Calculate the result of a mathematical expression.

        Args:
            expression: The mathematical expression to calculate, such as '2 + 2'. The expression can contain numbers, operators (+, -, *, /), parentheses, and spaces.

        Returns:
            The result of the mathematical expression.

        Raises:
            ValueError: If the expression is invalid.
        """
        if not all(char in "0123456789+-*/(). " for char in expression):
            raise ValueError("Invalid characters in expression")
        return str(round(float(eval(expression, {"__builtins__": None}, {})), 2))

    def cancel_pending_order(self, order_id: str, reason: str) -> Order:
        """Cancel a pending order. If the order is already processed or delivered,
        it cannot be cancelled. The agent needs to explain the cancellation detail
        and ask for explicit user confirmation (yes/no) to proceed. If the user confirms,
        the order status will be changed to 'cancelled' and the payment will be refunded.
        The refund will be added to the user's gift card balance immediately if the payment
        was made using a gift card, otherwise the refund would take 5-7 business days to process.
        The function returns the order details after the cancellation.

        Args:
            order_id: The order id, such as '#W0000000'. Be careful there is a '#' symbol at the beginning of the order id.
            reason: The reason for cancellation, which should be either 'no longer needed' or 'ordered by mistake'.

        Returns:
            Order: The order details after the cancellation.
        """
        order = self._get_order(order_id)
        if order.status != "pending":
            raise ValueError("Non-pending order cannot be cancelled")

        if reason not in {"no longer needed", "ordered by mistake"}:
            raise ValueError("Invalid reason")

        refunds = []
        for payment in order.payment_history:
            payment_id = payment.payment_method_id
            refund = OrderPayment(
                transaction_type="refund",
                amount=payment.amount,
                payment_method_id=payment_id,
            )
            refunds.append(refund)
            user = self._get_user(order.user_id)
            payment_method = self._get_payment_method(user.user_id, payment_id)
            if isinstance(payment_method, GiftCard):
                payment_method.balance += payment.amount
                payment_method.balance = round(payment_method.balance, 2)

        order.status = "cancelled"
        order.cancel_reason = reason
        order.payment_history.extend(refunds)

        return order

    def exchange_delivered_order_items(
        self,
        order_id: str,
        item_ids: List[str],
        new_item_ids: List[str],
        payment_method_id: str,
    ) -> Order:
        """Exchange items in a delivered order to new items of the same product type.
        For a delivered order, return or exchange can be only done once by the agent.
        The agent needs to explain the exchange detail and ask for explicit user confirmation (yes/no) to proceed.

        Args:
            order_id: The order id, such as '#W0000000'. Be careful there is a '#' symbol at the beginning of the order id.
            item_ids: The item ids to be exchanged, each such as '1008292230'. There could be duplicate items in the list.
            new_item_ids: The item ids to be exchanged for, each such as '1008292230'.
                         There could be duplicate items in the list. Each new item id should match the item id
                         in the same position and be of the same product.
            payment_method_id: The payment method id to pay or receive refund for the item price difference,
                             such as 'gift_card_0000000' or 'credit_card_0000000'. These can be looked up
                             from the user or order details.

        Returns:
            Order: The order details after the exchange.

        Raises:
            ValueError: If the order is not delivered.
            ValueError: If the items to be exchanged do not exist.
            ValueError: If the new items do not exist or do not match the old items.
            ValueError: If the number of items to be exchanged does not match.
        """
        order = self._get_order(order_id)
        if order.status != "delivered":
            raise ValueError("Non-delivered order cannot be exchanged")

        all_item_ids = [item.item_id for item in order.items]
        for item_id in item_ids:
            if item_ids.count(item_id) > all_item_ids.count(item_id):
                raise ValueError(f"Number of {item_id} not found.")

        if len(item_ids) != len(new_item_ids):
            raise ValueError("The number of items to be exchanged should match.")

        diff_price = 0
        for item_id, new_item_id in zip(item_ids, new_item_ids):
            item = next((item for item in order.items if item.item_id == item_id), None)
            if item is None:
                raise ValueError(f"Item {item_id} not found")
            product_id = item.product_id
            variant = self._get_variant(product_id, new_item_id)
            if not variant.available:
                raise ValueError(f"New item {new_item_id} not found or available")

            old_price = item.price
            new_price = variant.price
            diff_price += new_price - old_price

        diff_price = round(diff_price, 2)

        payment_method = self._get_payment_method(order.user_id, payment_method_id)

        if isinstance(payment_method, GiftCard) and payment_method.balance < diff_price:
            raise ValueError(
                "Insufficient gift card balance to pay for the price difference"
            )

        order.status = "exchange requested"
        order.exchange_items = sorted(item_ids)
        order.exchange_new_items = sorted(new_item_ids)
        order.exchange_payment_method_id = payment_method_id
        order.exchange_price_difference = diff_price

        return order

    def find_user_id_by_name_zip(self, first_name: str, last_name: str, zip: str) -> str:
        """Find user id by first name, last name, and zip code. If the user is not found, the function
        will return an error message. By default, find user id by email, and only call this function
        if the user is not found by email or cannot remember email.

        Args:
            first_name: The first name of the customer, such as 'John'.
            last_name: The last name of the customer, such as 'Doe'.
            zip: The zip code of the customer, such as '12345'.

        Returns:
            str: The user id if found, otherwise an error message.

        Raises:
            ValueError: If the user is not found.
        """
        for user_id, user in self.db.users.items():
            if (
                user.name.first_name.lower() == first_name.lower()
                and user.name.last_name.lower() == last_name.lower()
                and user.address.zip == zip
            ):
                return user_id
        raise ValueError("User not found")

    def find_user_id_by_email(self, email: str) -> str:
        """Find user id by email. If the user is not found, the function will return an error message.

        Args:
            email: The email of the user, such as 'something@example.com'.

        Returns:
            str: The user id if found, otherwise an error message.

        Raises:
            ValueError: If the user is not found.
        """
        for user_id, user in self.db.users.items():
            if user.email.lower() == email.lower():
                return user_id
        raise ValueError("User not found")

    def get_order_details(self, order_id: str) -> Order:
        """Get the status and details of an order.

        Args:
            order_id: The order id, such as '#W0000000'. Be careful there is a '#' symbol at the beginning of the order id.

        Returns:
            Order: The order details.

        Raises:
            ValueError: If the order is not found.
        """
        order = self._get_order(order_id)
        return order

    def get_product_details(self, product_id: str) -> Product:
        """Get the inventory details of a product.

        Args:
            product_id: The product id, such as '6086499569'. Be careful the product id is different from the item id.

        Returns:
            Product: The product details.

        Raises:
            ValueError: If the product is not found.
        """
        product = self._get_product(product_id)
        return product

    def get_user_details(self, user_id: str) -> User:
        """Get the details of a user, including their orders.

        Args:
            user_id: The user id, such as 'sara_doe_496'.

        Returns:
            User: The user details.

        Raises:
            ValueError: If the user is not found.
        """
        user = self._get_user(user_id)
        return user

    def list_all_product_types(self) -> str:
        """List the name and product id of all product types.
        Each product type has a variety of different items with unique item ids and options.
        There are only 50 product types in the store.

        Returns:
            str: A JSON string mapping product names to their product IDs, sorted alphabetically by name.
        """
        product_dict = {
            product.name: product.product_id for product in self.db.products.values()
        }
        return json.dumps(product_dict, sort_keys=True)

    def modify_pending_order_address(
        self,
        order_id: str,
        address1: str,
        address2: str,
        city: str,
        state: str,
        country: str,
        zip: str,
    ) -> Order:
        """Modify the shipping address of a pending order. The agent needs to explain the modification detail and ask for explicit user confirmation (yes/no) to proceed.

        Args:
            order_id: The order id, such as '#W0000000'. Be careful there is a '#' symbol at the beginning of the order id.
            address1: The first line of the address, such as '123 Main St'.
            address2: The second line of the address, such as 'Apt 1' or ''.
            city: The city, such as 'San Francisco'.
            state: The state, such as 'CA'.
            country: The country, such as 'USA'.
            zip: The zip code, such as '12345'.

        Returns:
            Order: The order details after the modification.

        Raises:
            ValueError: If the order is not pending.
        """
        order = self._get_order(order_id)
        if not self._is_pending_order(order):
            raise ValueError("Non-pending order cannot be modified")

        order.address = UserAddress(
            address1=address1,
            address2=address2,
            city=city,
            state=state,
            country=country,
            zip=zip,
        )
        return order

    def modify_pending_order_items(
        self,
        order_id: str,
        item_ids: List[str],
        new_item_ids: List[str],
        payment_method_id: str,
    ) -> Order:
        """Modify items in a pending order to new items of the same product type. For a pending order, this function can only be called once. The agent needs to explain the exchange detail and ask for explicit user confirmation (yes/no) to proceed.

        Args:
            order_id: The order id, such as '#W0000000'. Be careful there is a '#' symbol at the beginning of the order id.
            item_ids: The item ids to be modified, each such as '1008292230'. There could be duplicate items in the list.
            new_item_ids: The item ids to be modified for, each such as '1008292230'. There could be duplicate items in the list. Each new item id should match the item id in the same position and be of the same product.
            payment_method_id: The payment method id to pay or receive refund for the item price difference, such as 'gift_card_0000000' or 'credit_card_0000000'. These can be looked up from the user or order details.

        Returns:
            Order: The order details after the modification.

        Raises:
            ValueError: If the order is not pending.
            ValueError: If the items to be modified do not exist.
            ValueError: If the new items do not exist or do not match the old items.
            ValueError: If the number of items to be modified does not match.
        """
        order = self._get_order(order_id)
        if order.status != "pending":
            raise ValueError("Non-pending order cannot be modified")

        all_item_ids = [item.item_id for item in order.items]
        for item_id in item_ids:
            if item_ids.count(item_id) > all_item_ids.count(item_id):
                raise ValueError(f"{item_id} not found")

        if len(item_ids) != len(new_item_ids):
            raise ValueError("The number of items to be exchanged should match")

        diff_price = 0
        for item_id, new_item_id in zip(item_ids, new_item_ids):
            if item_id == new_item_id:
                raise ValueError(
                    "The new item id should be different from the old item id"
                )
            item = next((item for item in order.items if item.item_id == item_id), None)
            if item is None:
                raise ValueError(f"Item {item_id} not found")
            product_id = item.product_id
            variant = self._get_variant(product_id, new_item_id)
            if not variant.available:
                raise ValueError(f"New item {new_item_id} not found or available")

            old_price = item.price
            new_price = variant.price
            diff_price += new_price - old_price

        payment_method = self._get_payment_method(order.user_id, payment_method_id)

        if isinstance(payment_method, GiftCard) and payment_method.balance < diff_price:
            raise ValueError("Insufficient gift card balance to pay for the new item")

        order.payment_history.append(
            OrderPayment(
                transaction_type="payment" if diff_price > 0 else "refund",
                amount=abs(diff_price),
                payment_method_id=payment_method_id,
            )
        )
        if isinstance(payment_method, GiftCard):
            payment_method.balance -= diff_price
            payment_method.balance = round(payment_method.balance, 2)

        for item_id, new_item_id in zip(item_ids, new_item_ids):
            item = next((item for item in order.items if item.item_id == item_id), None)
            if item is None:
                raise ValueError(f"Item {item_id} not found")
            item.item_id = new_item_id
            item.price = variant.price
            item.options = variant.options
        order.status = "pending (item modified)"

        return order

    def modify_pending_order_payment(
        self,
        order_id: str,
        payment_method_id: str,
    ) -> Order:
        """Modify the payment method of a pending order. The agent needs to explain the modification detail and ask for explicit user confirmation (yes/no) to proceed.

        Args:
            order_id: The order id, such as '#W0000000'. Be careful there is a '#' symbol at the beginning of the order id.
            payment_method_id: The payment method id to pay or receive refund for the item price difference, such as 'gift_card_0000000' or 'credit_card_0000000'. These can be looked up from the user or order details.

        Returns:
            Order: The order details after the modification.

        Raises:
            ValueError: If the order is not pending.
            ValueError: If the payment method does not exist.
            ValueError: If the payment history has more than one payment.
            ValueError: If the new payment method is the same as the current one.
        """
        order = self._get_order(order_id)

        if not self._is_pending_order(order):
            raise ValueError("Non-pending order cannot be modified")

        payment_method = self._get_payment_method(order.user_id, payment_method_id)

        if (
            len(order.payment_history) != 1
            or order.payment_history[0].transaction_type != "payment"
        ):
            raise ValueError("There should be exactly one payment for a pending order")

        if order.payment_history[0].payment_method_id == payment_method_id:
            raise ValueError(
                "The new payment method should be different from the current one"
            )

        amount = order.payment_history[0].amount

        if isinstance(payment_method, GiftCard) and payment_method.balance < amount:
            raise ValueError("Insufficient gift card balance to pay for the order")

        order.payment_history.extend(
            [
                OrderPayment(
                    transaction_type="payment",
                    amount=amount,
                    payment_method_id=payment_method_id,
                ),
                OrderPayment(
                    transaction_type="refund",
                    amount=amount,
                    payment_method_id=order.payment_history[0].payment_method_id,
                ),
            ]
        )

        if isinstance(payment_method, GiftCard):
            payment_method.balance -= amount
            payment_method.balance = round(payment_method.balance, 2)

        old_payment_method = self._get_payment_method(
            order.user_id, order.payment_history[0].payment_method_id
        )
        if isinstance(old_payment_method, GiftCard):
            old_payment_method.balance += amount
            old_payment_method.balance = round(old_payment_method.balance, 2)

        return order

    def modify_user_address(
        self,
        user_id: str,
        address1: str,
        address2: str,
        city: str,
        state: str,
        country: str,
        zip: str,
    ) -> User:
        """Modify the default address of a user. The agent needs to explain the modification detail and ask for explicit user confirmation (yes/no) to proceed.

        Args:
            user_id: The user id, such as 'sara_doe_496'.
            address1: The first line of the address, such as '123 Main St'.
            address2: The second line of the address, such as 'Apt 1' or ''.
            city: The city, such as 'San Francisco'.
            state: The state, such as 'CA'.
            country: The country, such as 'USA'.
            zip: The zip code, such as '12345'.

        Returns:
            User: The user details after the modification.

        Raises:
            ValueError: If the user is not found.
        """
        user = self._get_user(user_id)
        user.address = UserAddress(
            address1=address1,
            address2=address2,
            city=city,
            state=state,
            country=country,
            zip=zip,
        )
        return user

    def return_delivered_order_items(
        self,
        order_id: str,
        item_ids: List[str],
        payment_method_id: str,
    ) -> Order:
        """Return some items of a delivered order.
        The order status will be changed to 'return requested'.
        The agent needs to explain the return detail and ask for explicit user confirmation (yes/no) to proceed.
        The user will receive follow-up email for how and where to return the item.

        Args:
            order_id: The order id, such as '#W0000000'. Be careful there is a '#' symbol at the beginning of the order id.
            item_ids: The item ids to be returned, each such as '1008292230'. There could be duplicate items in the list.
            payment_method_id: The payment method id to pay or receive refund for the item price difference, such as 'gift_card_0000000' or 'credit_card_0000000'.
                             These can be looked up from the user or order details.

        Returns:
            Order: The order details after requesting the return.

        Raises:
            ValueError: If the order is not delivered.
            ValueError: If the payment method is not the original payment method or a gift card.
            ValueError: If the items to be returned do not exist.
        """
        order = self._get_order(order_id)
        if order.status != "delivered":
            raise ValueError("Non-delivered order cannot be returned")

        user = self._get_user(order.user_id)
        payment_method = self._get_payment_method(user.user_id, payment_method_id)

        if (
            not isinstance(payment_method, GiftCard)
            and payment_method_id != order.payment_history[0].payment_method_id
        ):
            raise ValueError("Payment method should be the original payment method")

        all_item_ids = [item.item_id for item in order.items]
        for item_id in item_ids:
            if item_ids.count(item_id) > all_item_ids.count(item_id):
                raise ValueError("Some item not found")

        order.status = "return requested"
        order.return_items = sorted(item_ids)
        order.return_payment_method_id = payment_method_id

        return order

    def transfer_to_human_agents(self, summary: str) -> str:
        """
        Transfer the user to a human agent, with a summary of the user's issue.
        Only transfer if
         -  the user explicitly asks for a human agent
         -  given the policy and the available tools, you cannot solve the user's issue.

        Args:
            summary: A summary of the user's issue.

        Returns:
            A message indicating the user has been transferred to a human agent.
        """
        return "Transfer successful"


def _tool_description(tool_name: str, fallback: str) -> str:
    method = getattr(RetailTools, tool_name, None)
    if method is None:
        return fallback
    return inspect.getdoc(method) or fallback


@mcp.tool(description=_tool_description("find_user_id_by_email", "Find user id by email."))
def find_user_id_by_email(email: str, session_id: str = "") -> str:
    tools = RetailTools(get_db(session_id))
    return tools.find_user_id_by_email(email)


@mcp.tool(description=_tool_description("find_user_id_by_name_zip", "Find user id by first name, last name, and zip code."))
def find_user_id_by_name_zip(
    first_name: str,
    last_name: str,
    zip: str = "",
    zip_code: str = "",
    session_id: str = "",
) -> str:
    tools = RetailTools(get_db(session_id))
    resolved_zip = zip or zip_code
    if not resolved_zip:
        raise ValueError("Missing required argument: zip")
    return tools.find_user_id_by_name_zip(first_name, last_name, resolved_zip)


@mcp.tool(description=_tool_description("get_order_details", "Get the status and details of an order."))
def get_order_details(order_id: str, session_id: str = "") -> str:
    tools = RetailTools(get_db(session_id))
    order = tools.get_order_details(order_id)
    return order.model_dump_json(indent=2)


@mcp.tool(description=_tool_description("get_product_details", "Get the inventory details of a product."))
def get_product_details(product_id: str, session_id: str = "") -> str:
    tools = RetailTools(get_db(session_id))
    product = tools.get_product_details(product_id)
    return product.model_dump_json(indent=2)


@mcp.tool(description=_tool_description("get_user_details", "Get the details of a user, including their orders."))
def get_user_details(user_id: str, session_id: str = "") -> str:
    tools = RetailTools(get_db(session_id))
    user = tools.get_user_details(user_id)
    return user.model_dump_json(indent=2)


@mcp.tool(description=_tool_description("list_all_product_types", "List the name and product id of all product types."))
def list_all_product_types(session_id: str = "") -> str:
    tools = RetailTools(get_db(session_id))
    return tools.list_all_product_types()


@mcp.tool(description=_tool_description("calculate", "Calculate the result of a mathematical expression."))
def calculate(expression: str, session_id: str = "") -> str:
    tools = RetailTools(get_db(session_id))
    return tools.calculate(expression)


@mcp.tool(description=_tool_description("transfer_to_human_agents", "Transfer the user to a human agent."))
def transfer_to_human_agents(summary: str, session_id: str = "") -> str:
    tools = RetailTools(get_db(session_id))
    return tools.transfer_to_human_agents(summary)


@mcp.tool(description=_tool_description("cancel_pending_order", "Cancel a pending order."))
def cancel_pending_order(order_id: str, reason: str, session_id: str = "") -> str:
    db = get_db(session_id)
    tools = RetailTools(db)
    order = tools.cancel_pending_order(order_id, reason)
    db.save()
    return order.model_dump_json(indent=2)


@mcp.tool(description=_tool_description("exchange_delivered_order_items", "Exchange items in a delivered order."))
def exchange_delivered_order_items(
    order_id: str,
    item_ids: List[str],
    new_item_ids: List[str],
    payment_method_id: str,
    session_id: str = "",
) -> str:
    db = get_db(session_id)
    tools = RetailTools(db)
    order = tools.exchange_delivered_order_items(
        order_id=order_id,
        item_ids=item_ids,
        new_item_ids=new_item_ids,
        payment_method_id=payment_method_id,
    )
    db.save()
    return order.model_dump_json(indent=2)


@mcp.tool(description=_tool_description("return_delivered_order_items", "Return some items of a delivered order."))
def return_delivered_order_items(
    order_id: str,
    item_ids: List[str],
    payment_method_id: str,
    session_id: str = "",
) -> str:
    db = get_db(session_id)
    tools = RetailTools(db)
    order = tools.return_delivered_order_items(
        order_id=order_id,
        item_ids=item_ids,
        payment_method_id=payment_method_id,
    )
    db.save()
    return order.model_dump_json(indent=2)


@mcp.tool(description=_tool_description("modify_pending_order_items", "Modify items in a pending order."))
def modify_pending_order_items(
    order_id: str,
    item_ids: List[str],
    new_item_ids: List[str],
    payment_method_id: str,
    session_id: str = "",
) -> str:
    db = get_db(session_id)
    tools = RetailTools(db)
    order = tools.modify_pending_order_items(
        order_id=order_id,
        item_ids=item_ids,
        new_item_ids=new_item_ids,
        payment_method_id=payment_method_id,
    )
    db.save()
    return order.model_dump_json(indent=2)


@mcp.tool(description=_tool_description("modify_pending_order_address", "Modify the shipping address of a pending order."))
def modify_pending_order_address(
    order_id: str,
    address1: str,
    address2: str,
    city: str,
    state: str,
    country: str,
    zip: str,
    session_id: str = "",
) -> str:
    db = get_db(session_id)
    tools = RetailTools(db)
    order = tools.modify_pending_order_address(
        order_id=order_id,
        address1=address1,
        address2=address2,
        city=city,
        state=state,
        country=country,
        zip=zip,
    )
    db.save()
    return order.model_dump_json(indent=2)


@mcp.tool(description=_tool_description("modify_pending_order_payment", "Modify the payment method of a pending order."))
def modify_pending_order_payment(
    order_id: str,
    payment_method_id: str,
    session_id: str = "",
) -> str:
    db = get_db(session_id)
    tools = RetailTools(db)
    order = tools.modify_pending_order_payment(
        order_id=order_id,
        payment_method_id=payment_method_id,
    )
    db.save()
    return order.model_dump_json(indent=2)


@mcp.tool(description=_tool_description("modify_user_address", "Modify the default address of a user."))
def modify_user_address(
    user_id: str,
    address1: str,
    address2: str,
    city: str,
    state: str,
    country: str,
    zip: str,
    session_id: str = "",
) -> str:
    db = get_db(session_id)
    tools = RetailTools(db)
    user = tools.modify_user_address(
        user_id=user_id,
        address1=address1,
        address2=address2,
        city=city,
        state=state,
        country=country,
        zip=zip,
    )
    db.save()
    return user.model_dump_json(indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retail MCP Server (tau2 default)")
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help="Path to the retail database JSON file",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5050,
        help="Port to run the SSE server on",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to",
    )
    parser.add_argument(
        "--transport",
        choices=["sse", "stdio"],
        default="sse",
        help="Transport protocol to use",
    )

    args = parser.parse_args()

    os.environ["RETAIL_DB_PATH"] = args.db_path

    get_db()
    print("   Original DB file is READ-ONLY (per-session copies used for mutations)")
    print(f"   Session DB dir: {SESSION_DB_DIR}")

    print("\n🚀 Starting Retail MCP Server (tau2 default)...")
    print(f"   Transport: {args.transport}")
    if args.transport == "sse":
        print(f"   Host: {args.host}")
        print(f"   Port: {args.port}")
        print(f"   SSE endpoint: http://{args.host}:{args.port}/sse")

    mcp.run(transport=args.transport, host=args.host, port=args.port)
