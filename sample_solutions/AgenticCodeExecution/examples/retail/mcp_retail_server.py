#!/usr/bin/env python3
"""
MCP Server for Retail Tools - Fully Standalone

All business logic is directly in the MCP tools - no intermediate wrapper classes.
"""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

# Add parent directory to sys.path for shared modules (error_hints)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retail_data_model import (
    RetailDB,
    Order,
    OrderItem,
    UserName,
    User,
    Product,
    Variant,
    CreditCard,
    PaypalAccount,
    GiftCard,
    OrderPayment,
    OrderFullfilment,
    UserAddress,
)
from error_hints import analyze_execution_error


# Default DB path (sibling data/ directory)
DEFAULT_DB_PATH = str(Path(__file__).resolve().parent / "data" / "db.json")

TAU2_BENCH_URL = (
    "https://raw.githubusercontent.com/sierra-research/tau2-bench/"
    "main/data/tau2/domains/retail/db.json"
)


def ensure_db(db_path: str) -> None:
    """Check that the retail database exists; auto-download from tau2-bench if missing."""
    p = Path(db_path)
    if p.exists():
        return
    print(f"⚠️  Database not found: {db_path}")
    print(f"   Downloading from tau2-bench …")
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlretrieve(TAU2_BENCH_URL, str(p))
        print(f"   ✅ Downloaded ({p.stat().st_size / 1_048_576:.1f} MB)")
    except Exception as exc:
        print(f"   ❌ Download failed: {exc}")
        print(f"   Please download manually:")
        print(f"      curl -L -o {db_path} {TAU2_BENCH_URL}")
        sys.exit(1)


# Create the MCP server
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
modifying orders or processing returns/exchanges."""
)

# Global database state
_db: Optional[RetailDB] = None  # Read-only template DB
_original_db_path: str = ""  # Path to the original pristine DB file
_session_dbs: Dict[str, RetailDB] = {}  # Per-session DB copies
SESSION_DB_DIR = Path(__file__).resolve().parent.parent / "session_dbs"
SESSION_DB_DIR.mkdir(exist_ok=True)


def _normalize_order_id(order_id: str) -> str:
    """Ensure order_id starts with '#'. Agents frequently omit it."""
    order_id = order_id.strip()
    if order_id and not order_id.startswith("#"):
        order_id = "#" + order_id
    return order_id


def _session_db_file(session_id: str) -> Path:
    safe = "".join(ch for ch in session_id if ch.isalnum() or ch in ("-", "_"))
    if not safe:
        safe = "session"
    return SESSION_DB_DIR / f"{safe[:64]}.json"


def get_db(session_id: str = "") -> RetailDB:
    """Get the database for a given session.

    If session_id is empty, returns the read-only template DB.
    If session_id is provided, returns a per-session pristine copy
    (created on first access from the original file).
    This ensures each benchmark task gets its own clean database state.
    """
    global _db, _original_db_path

    # Initialize template if needed
    if _db is None:
        db_path = os.environ.get("RETAIL_DB_PATH", DEFAULT_DB_PATH)
        _original_db_path = db_path
        _db = RetailDB.load(db_path)
        _db._db_path = ""  # Prevent accidental writes to original file
        print(f"Loaded template database from {db_path}")
        print(f"  - {len(_db.products)} products")
        print(f"  - {len(_db.users)} users")
        print(f"  - {len(_db.orders)} orders")

    if not session_id:
        return _db

    if session_id not in _session_dbs:
        # Load fresh pristine copy from the original file
        db = RetailDB.load(_original_db_path)
        session_db_file = _session_db_file(session_id)
        db._db_path = str(session_db_file)
        _session_dbs[session_id] = db
        print(f"🆕 Created pristine DB for session {session_id[:8]}... "
              f"({len(_session_dbs)} active sessions)")

    return _session_dbs[session_id]


def _get_data_model_defs() -> Dict[str, dict]:
    model_classes = [
        Variant,
        Product,
        UserName,
        UserAddress,
        CreditCard,
        PaypalAccount,
        GiftCard,
        User,
        OrderItem,
        OrderPayment,
        OrderFullfilment,
        Order,
    ]
    defs: Dict[str, dict] = {}
    for model_cls in model_classes:
        schema = model_cls.model_json_schema(ref_template="#/$defs/{model}")
        defs[model_cls.__name__] = {
            "description": schema.get("description", ""),
            "properties": schema.get("properties", {}),
        }
    return defs


def _get_tool_metadata_payload() -> Dict[str, Any]:
    ordered_actions = [
        "calculate",
        "cancel_pending_order",
        "exchange_delivered_order_items",
        "find_user_id_by_email",
        "find_user_id_by_name_zip",
        "get_order_details",
        "get_product_details",
        "get_user_details",
        "list_all_product_types",
        "modify_pending_order_address",
        "modify_pending_order_items",
        "modify_pending_order_payment",
        "modify_user_address",
        "return_delivered_order_items",
        "transfer_to_human_agents",
    ]

    return {
        "ordered_actions": ordered_actions,
        "return_types": {
            "calculate": "str",
            "cancel_pending_order": "str (JSON)",
            "exchange_delivered_order_items": "str (JSON)",
            "find_user_id_by_email": "str",
            "find_user_id_by_name_zip": "str",
            "get_order_details": "str (JSON)",
            "get_product_details": "str (JSON)",
            "get_user_details": "str (JSON)",
            "list_all_product_types": "str (JSON)",
            "modify_pending_order_address": "str (JSON)",
            "modify_pending_order_items": "str (JSON)",
            "modify_pending_order_payment": "str (JSON)",
            "modify_user_address": "str (JSON)",
            "return_delivered_order_items": "str (JSON)",
            "transfer_to_human_agents": "str",
        },
        "semantic_types": {
            "cancel_pending_order": "Order",
            "exchange_delivered_order_items": "Order",
            "get_order_details": "Order",
            "get_product_details": "Product",
            "get_user_details": "User",
            "list_all_product_types": "dict[name, product_id]",
            "modify_pending_order_address": "Order",
            "modify_pending_order_items": "Order",
            "modify_pending_order_payment": "Order",
            "modify_user_address": "User",
            "return_delivered_order_items": "Order",
        },
        "data_model_defs": _get_data_model_defs(),
    }


# ==================== READ TOOLS ====================

@mcp.tool()
def find_user_id_by_email(email: str, session_id: str = "") -> str:
    """Find user id by email. Use this first to identify a customer.
    
    Args:
        email: The email of the user, such as 'something@example.com'.

    Usage example:
        user_id = actions.find_user_id_by_email("real_email_from_user@example.com")
        print(user_id)

    Notes:
        - Use a real value obtained from the user.
        - Do NOT use placeholders like "email" or "user@example.com" unless user provided it.
        
    Returns:
        The user id if found.
    """
    db = get_db(session_id)
    for user_id, user in db.users.items():
        if user.email.lower() == email.lower():
            return user_id
    raise ValueError("User not found")


@mcp.tool()
def find_user_id_by_name_zip(first_name: str, last_name: str, zip_code: str, session_id: str = "") -> str:
    """Find user id by first name, last name, and zip code. 
    Use this if the customer cannot remember their email.
    
    Args:
        first_name: The first name of the customer, such as 'John'.
        last_name: The last name of the customer, such as 'Doe'.
        zip_code: The zip code of the customer, such as '12345'.

    Usage example:
        user_id = actions.find_user_id_by_name_zip("RealFirst", "RealLast", "12345")
        print(user_id)

    Notes:
        - All three fields must come from the user.
        - Do NOT use placeholders like "first_name", "last_name", "zip_code" as values.
        
    Returns:
        The user id if found.
    """
    db = get_db(session_id)
    for user_id, user in db.users.items():
        if (
            user.name.first_name.lower() == first_name.lower()
            and user.name.last_name.lower() == last_name.lower()
            and user.address.zip == zip_code
        ):
            return user_id
    raise ValueError("User not found")


@mcp.tool()
def get_order_details(order_id: str, session_id: str = "") -> str:
    """Returns JSON with order info where items is a LIST of {item_id, product_id, price, ...} dicts and status is a string

    Args:
        order_id: The order id, such as '#W0000000'. Include the '#' symbol.

    Example:
        import json
        order = json.loads(actions.get_order_details("#W1234567"))
        print(order['status'])  # 'pending', 'delivered', 'cancelled', etc.
        for item in order['items']:  # list of dicts
            print(f"Item {item['item_id']}: ${item['price']}")
        # order['payment_history'] = [{"payment_method_id": "credit_card_123", "amount": 29.99}]
    """
    order_id = _normalize_order_id(order_id)
    db = get_db(session_id)
    if order_id not in db.orders:
        raise ValueError("Order not found")
    return db.orders[order_id].model_dump_json(indent=2)


@mcp.tool()
def get_product_details(product_id: str, session_id: str = "") -> str:
    """Returns JSON with product info where variants is a DICT {item_id: info} — use .items() to iterate, NOT a list

    Args:
        product_id: The product id (numeric string). Get IDs from list_all_product_types(). Different from item_id.

    Example:
        import json
        product = json.loads(actions.get_product_details(product_id))
        for item_id, variant in product['variants'].items():
            print(f"{item_id}: ${variant['price']} - {variant['options']} - Available: {variant['available']}")
        print(f"Total variants: {len(product['variants'])}")
    """
    db = get_db(session_id)
    if product_id not in db.products:
        raise ValueError("Product not found")
    return db.products[product_id].model_dump_json(indent=2)


@mcp.tool()
def get_user_details(user_id: str, session_id: str = "") -> str:
    """Returns JSON with user info where orders is a list of ID strings and payment_methods is a DICT {pm_id: info} — use .items()

    Args:
        user_id: The user id, such as 'sara_doe_496'.

    Example:
        import json
        user = json.loads(actions.get_user_details(user_id))
        print(user['name'])  # {"first_name": "Sara", "last_name": "Doe"}
        for order_id in user['orders']:  # list of strings like "#W0001"
            print(order_id)
        for pm_id, pm_info in user['payment_methods'].items():
            print(f"{pm_id}: {pm_info}")
    """
    db = get_db(session_id)
    if user_id not in db.users:
        raise ValueError("User not found")
    return db.users[user_id].model_dump_json(indent=2)


@mcp.tool()
def list_all_product_types(session_id: str = "") -> str:
    """Returns JSON dict {name: product_id} — use .items() to iterate, NOT a list

    Example:
        import json
        types = json.loads(actions.list_all_product_types())
        # types = {"T-Shirt": "1001", "Jeans": "1002", ...}
        for name, product_id in types.items():
            print(f"{name}: {product_id}")
        # To get full details: actions.get_product_details(product_id)
    """
    db = get_db(session_id)
    product_dict = {
        product.name: product.product_id for product in db.products.values()
    }
    return json.dumps(product_dict, sort_keys=True)


# ==================== UTILITY TOOLS ====================

@mcp.tool()
def calculate(expression: str, session_id: str = "") -> str:
    """Calculate the result of a mathematical expression.
    
    Args:
        expression: The mathematical expression, such as '2 + 2' or '100 * 0.1'.
        
    Returns:
        The calculated result as a string.
    """
    if not all(char in "0123456789+-*/(). " for char in expression):
        raise ValueError("Invalid characters in expression")
    return str(round(float(eval(expression, {"__builtins__": None}, {})), 2))


@mcp.tool()
def transfer_to_human_agents(summary: str, session_id: str = "") -> str:
    """Transfer the customer to a human agent.
    Only use this if the customer explicitly asks for a human agent, or 
    if you cannot solve their issue with the available tools.
    
    Args:
        summary: A summary of the customer's issue.
        
    Returns:
        Confirmation message.
    """
    return "Transfer successful"


@mcp.tool()
def get_execution_error_hint(error_msg: str, code: str = "", session_id: str = "") -> str:
    """Return a recovery hint for sandbox execution/tool errors.

    Args:
        error_msg: The root error message produced by sandbox/tool execution.
        code: The executed python code snippet (optional, used for pattern detection).

    Returns:
        str: A concise hint string. Empty string if no specific hint applies.
    """
    return analyze_execution_error(error_msg=error_msg, code=code, domain="retail")


@mcp.tool()
def get_tool_metadata(session_id: str = "") -> str:
    """Return metadata used to build execute_python action/data-model description.

    Returns:
        JSON string with keys like return_types and data_model_defs.
    """
    return json.dumps(_get_tool_metadata_payload())


# ==================== WRITE TOOLS ====================

@mcp.tool()
def cancel_pending_order(order_id: str, reason: str, session_id: str = "") -> str:
    """Cancel a pending order. The order must be in 'pending' status.
    Ask the customer for confirmation before cancelling.
    
    Args:
        order_id: The order id, such as '#W0000000'. Include the '#' symbol.
        reason: Either 'no longer needed' or 'ordered by mistake'.
        
    Returns:
        A JSON STRING (not a dict). You MUST parse it: order = json.loads(result)
        Contains updated order details showing cancelled status.
    """
    order_id = _normalize_order_id(order_id)
    db = get_db(session_id)
    
    if order_id not in db.orders:
        raise ValueError("Order not found")
    order = db.orders[order_id]
    
    if order.status != "pending":
        raise ValueError("Non-pending order cannot be cancelled")
    
    if reason not in {"no longer needed", "ordered by mistake"}:
        raise ValueError("Invalid reason")
    
    # Handle refunds
    refunds = []
    for payment in order.payment_history:
        payment_id = payment.payment_method_id
        refund = OrderPayment(
            transaction_type="refund",
            amount=payment.amount,
            payment_method_id=payment_id,
        )
        refunds.append(refund)
        
        # Refund to gift card immediately
        user = db.users[order.user_id]
        if payment_id in user.payment_methods:
            pm = user.payment_methods[payment_id]
            if isinstance(pm, GiftCard):
                pm.balance += payment.amount
                pm.balance = round(pm.balance, 2)
    
    order.status = "cancelled"
    order.cancel_reason = reason
    order.payment_history.extend(refunds)
    
    db.save()  # Persist changes to disk
    return order.model_dump_json(indent=2)


@mcp.tool()
def exchange_delivered_order_items(
    order_id: str,
    item_ids: List[str],
    new_item_ids: List[str],
    payment_method_id: str,
    session_id: str = "",
) -> str:
    """Exchange items in a delivered order for new items of the same product type.
    Ask the customer for confirmation before processing.
    
    Args:
        order_id: The order id, such as '#W0000000'. Include the '#' symbol.
        item_ids: List of item IDs to exchange, such as ['1008292230'].
        new_item_ids: List of new item IDs to exchange for. Must match positions.
        payment_method_id: Payment method ID for any price difference. MUST be a real ID from get_user_details() → user['payment_methods'] (e.g., 'credit_card_9513926', 'gift_card_1234567'). NEVER guess or use placeholders.
        
    Returns:
        A JSON STRING (not a dict). You MUST parse it: order = json.loads(result)
        Contains updated order details showing exchange requested status.
    """
    order_id = _normalize_order_id(order_id)
    db = get_db(session_id)
    
    if order_id not in db.orders:
        raise ValueError("Order not found")
    order = db.orders[order_id]
    
    if order.status != "delivered":
        raise ValueError("Non-delivered order cannot be exchanged")
    
    # Check items exist
    all_item_ids = [item.item_id for item in order.items]
    for item_id in item_ids:
        if item_ids.count(item_id) > all_item_ids.count(item_id):
            raise ValueError(f"Number of {item_id} not found.")
    
    if len(item_ids) != len(new_item_ids):
        raise ValueError("The number of items to be exchanged should match.")
    
    # Calculate price difference
    diff_price = 0
    for item_id, new_item_id in zip(item_ids, new_item_ids):
        item = next((i for i in order.items if i.item_id == item_id), None)
        if item is None:
            raise ValueError(f"Item {item_id} not found")
        
        product = db.products.get(item.product_id)
        if not product or new_item_id not in product.variants:
            raise ValueError(f"New item {new_item_id} not found")
        
        variant = product.variants[new_item_id]
        if not variant.available:
            raise ValueError(f"New item {new_item_id} not available")
        
        diff_price += variant.price - item.price
    
    diff_price = round(diff_price, 2)
    
    # Check payment method
    user = db.users[order.user_id]
    if payment_method_id not in user.payment_methods:
        raise ValueError("Payment method not found")
    
    pm = user.payment_methods[payment_method_id]
    if isinstance(pm, GiftCard) and pm.balance < diff_price:
        raise ValueError("Insufficient gift card balance for price difference")
    
    order.status = "exchange requested"
    order.exchange_items = sorted(item_ids)
    order.exchange_new_items = sorted(new_item_ids)
    order.exchange_payment_method_id = payment_method_id
    order.exchange_price_difference = diff_price
    
    db.save()  # Persist changes to disk
    return order.model_dump_json(indent=2)


@mcp.tool()
def return_delivered_order_items(
    order_id: str,
    item_ids: List[str],
    payment_method_id: str,
    session_id: str = "",
) -> str:
    """Return items from a delivered order.
    Ask the customer for confirmation before processing.
    
    Args:
        order_id: The order id, such as '#W0000000'. Include the '#' symbol.
        item_ids: List of item IDs to return, such as ['1008292230'].
        payment_method_id: Payment method ID for refund. Must be original payment or a gift card. MUST be a real ID from get_user_details() → user['payment_methods'] (e.g., 'credit_card_9513926', 'gift_card_1234567'). NEVER guess or use placeholders.
        
    Returns:
        A JSON STRING (not a dict). You MUST parse it: order = json.loads(result)
        Contains updated order details showing return requested status.
    """
    order_id = _normalize_order_id(order_id)
    db = get_db(session_id)
    
    if order_id not in db.orders:
        raise ValueError("Order not found")
    order = db.orders[order_id]
    
    if order.status != "delivered":
        raise ValueError("Non-delivered order cannot be returned")
    
    # Check payment method
    user = db.users[order.user_id]
    if payment_method_id not in user.payment_methods:
        raise ValueError("Payment method not found")
    
    pm = user.payment_methods[payment_method_id]
    if (
        not isinstance(pm, GiftCard)
        and payment_method_id != order.payment_history[0].payment_method_id
    ):
        raise ValueError("Payment method should be the original payment method")
    
    # Check items exist
    all_item_ids = [item.item_id for item in order.items]
    for item_id in item_ids:
        if item_ids.count(item_id) > all_item_ids.count(item_id):
            raise ValueError("Some item not found")
    
    order.status = "return requested"
    order.return_items = sorted(item_ids)
    order.return_payment_method_id = payment_method_id
    
    db.save()  # Persist changes to disk
    return order.model_dump_json(indent=2)


@mcp.tool()
def modify_pending_order_items(
    order_id: str,
    item_ids: List[str],
    new_item_ids: List[str],
    payment_method_id: str,
    session_id: str = "",
) -> str:
    """Modify items in a pending order to new items of the same product type.
    Can only be done once per order. Ask for confirmation before modifying.
    
    Args:
        order_id: The order id, such as '#W0000000'. Include the '#' symbol.
        item_ids: List of item IDs to modify, such as ['1008292230'].
        new_item_ids: List of new item IDs. Must match positions and be different items.
        payment_method_id: Payment method ID for any price difference. MUST be a real ID from get_user_details() → user['payment_methods'] (e.g., 'credit_card_9513926', 'gift_card_1234567'). NEVER guess or use placeholders.
        
    Returns:
        A JSON STRING (not a dict). You MUST parse it: order = json.loads(result)
        Contains updated order details.
    """
    order_id = _normalize_order_id(order_id)
    db = get_db(session_id)
    
    if order_id not in db.orders:
        raise ValueError("Order not found")
    order = db.orders[order_id]
    
    if order.status != "pending":
        raise ValueError("Non-pending order cannot be modified")
    
    # Check items exist
    all_item_ids = [item.item_id for item in order.items]
    for item_id in item_ids:
        if item_ids.count(item_id) > all_item_ids.count(item_id):
            raise ValueError(f"{item_id} not found")
    
    if len(item_ids) != len(new_item_ids):
        raise ValueError("The number of items to be exchanged should match")
    
    # Calculate price difference and validate
    diff_price = 0
    for item_id, new_item_id in zip(item_ids, new_item_ids):
        if item_id == new_item_id:
            raise ValueError("The new item id should be different from the old item id")
        
        item = next((i for i in order.items if i.item_id == item_id), None)
        if item is None:
            raise ValueError(f"Item {item_id} not found")
        
        product = db.products.get(item.product_id)
        if not product or new_item_id not in product.variants:
            raise ValueError(f"New item {new_item_id} not found")
        
        variant = product.variants[new_item_id]
        if not variant.available:
            raise ValueError(f"New item {new_item_id} not available")
        
        diff_price += variant.price - item.price
    
    # Check payment method
    user = db.users[order.user_id]
    if payment_method_id not in user.payment_methods:
        raise ValueError("Payment method not found")
    
    pm = user.payment_methods[payment_method_id]
    if isinstance(pm, GiftCard) and pm.balance < diff_price:
        raise ValueError("Insufficient gift card balance to pay for the new item")
    
    # Add payment record
    order.payment_history.append(
        OrderPayment(
            transaction_type="payment" if diff_price > 0 else "refund",
            amount=abs(diff_price),
            payment_method_id=payment_method_id,
        )
    )
    
    if isinstance(pm, GiftCard):
        pm.balance -= diff_price
        pm.balance = round(pm.balance, 2)
    
    # Update items
    for item_id, new_item_id in zip(item_ids, new_item_ids):
        item = next((i for i in order.items if i.item_id == item_id), None)
        product = db.products[item.product_id]
        variant = product.variants[new_item_id]
        
        item.item_id = new_item_id
        item.price = variant.price
        item.options = variant.options
    
    order.status = "pending (item modified)"
    
    db.save()  # Persist changes to disk
    return order.model_dump_json(indent=2)


@mcp.tool()
def modify_pending_order_address(
    order_id: str,
    address1: str,
    address2: str,
    city: str,
    state: str,
    country: str,
    zip_code: str,
    session_id: str = "",
) -> str:
    """Modify the shipping address of a pending order.
    Ask for confirmation before modifying.
    
    Args:
        order_id: The order id, such as '#W0000000'. Include the '#' symbol.
        address1: First line of address, such as '123 Main St'.
        address2: Second line of address, such as 'Apt 1' or empty string.
        city: City name.
        state: State abbreviation, such as 'CA'.
        country: Country, such as 'USA'.
        zip_code: ZIP code, such as '12345'.
        
    Returns:
        A JSON STRING (not a dict). You MUST parse it: order = json.loads(result)
        Contains updated order details.
    """
    order_id = _normalize_order_id(order_id)
    db = get_db(session_id)
    
    if order_id not in db.orders:
        raise ValueError("Order not found")
    order = db.orders[order_id]
    
    if "pending" not in order.status:
        raise ValueError("Non-pending order cannot be modified")
    
    order.address = UserAddress(
        address1=address1,
        address2=address2,
        city=city,
        state=state,
        country=country,
        zip=zip_code,
    )
    
    db.save()  # Persist changes to disk
    return order.model_dump_json(indent=2)


@mcp.tool()
def modify_pending_order_payment(order_id: str, payment_method_id: str, session_id: str = "") -> str:
    """Modify the payment method of a pending order.
    Ask for confirmation before modifying.
    
    Args:
        order_id: The order id, such as '#W0000000'. Include the '#' symbol.
        payment_method_id: New payment method ID. MUST be a real ID from get_user_details() → user['payment_methods'] (e.g., 'credit_card_9513926', 'gift_card_1234567'). NEVER guess or use placeholders.
        
    Returns:
        A JSON STRING (not a dict). You MUST parse it: order = json.loads(result)
        Contains updated order details.
    """
    order_id = _normalize_order_id(order_id)
    db = get_db(session_id)
    
    if order_id not in db.orders:
        raise ValueError("Order not found")
    order = db.orders[order_id]
    
    if "pending" not in order.status:
        raise ValueError("Non-pending order cannot be modified")
    
    # Check payment method exists
    user = db.users[order.user_id]
    if payment_method_id not in user.payment_methods:
        raise ValueError("Payment method not found")
    
    pm = user.payment_methods[payment_method_id]
    
    # Validate payment history
    if (
        len(order.payment_history) != 1
        or order.payment_history[0].transaction_type != "payment"
    ):
        raise ValueError("There should be exactly one payment for a pending order")
    
    if order.payment_history[0].payment_method_id == payment_method_id:
        raise ValueError("The new payment method should be different from the current one")
    
    amount = order.payment_history[0].amount
    
    if isinstance(pm, GiftCard) and pm.balance < amount:
        raise ValueError("Insufficient gift card balance to pay for the order")
    
    # Add new payment and refund records
    order.payment_history.extend([
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
    ])
    
    # Update gift card balances
    if isinstance(pm, GiftCard):
        pm.balance -= amount
        pm.balance = round(pm.balance, 2)
    
    old_pm_id = order.payment_history[0].payment_method_id
    if old_pm_id in user.payment_methods:
        old_pm = user.payment_methods[old_pm_id]
        if isinstance(old_pm, GiftCard):
            old_pm.balance += amount
            old_pm.balance = round(old_pm.balance, 2)
    
    db.save()  # Persist changes to disk
    return order.model_dump_json(indent=2)


@mcp.tool()
def modify_user_address(
    user_id: str,
    address1: str,
    address2: str,
    city: str,
    state: str,
    country: str,
    zip_code: str,
    session_id: str = "",
) -> str:
    """Modify the default address of a user.
    Ask for confirmation before modifying.
    
    Args:
        user_id: The user id, such as 'sara_doe_496'.
        address1: First line of address.
        address2: Second line of address.
        city: City name.
        state: State abbreviation.
        country: Country.
        zip_code: ZIP code.
        
    Returns:
        A JSON STRING (not a dict). You MUST parse it: user = json.loads(result)
        Contains updated user details.
    """
    db = get_db(session_id)
    
    if user_id not in db.users:
        raise ValueError("User not found")
    user = db.users[user_id]
    
    user.address = UserAddress(
        address1=address1,
        address2=address2,
        city=city,
        state=state,
        country=country,
        zip=zip_code,
    )
    
    db.save()  # Persist changes to disk
    return user.model_dump_json(indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retail MCP Server")
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help="Path to the retail database JSON file"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5050,
        help="Port to run the SSE server on"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to"
    )
    parser.add_argument(
        "--transport",
        choices=["sse", "stdio"],
        default="sse",
        help="Transport protocol to use"
    )
    
    args = parser.parse_args()
    
    # Set DB path via environment variable
    os.environ["RETAIL_DB_PATH"] = args.db_path
    
    # Ensure DB exists (auto-download from tau2-bench if missing)
    ensure_db(args.db_path)
    
    # Initialize template DB (read-only, never written to)
    get_db()
    print(f"   Original DB file is READ-ONLY (per-session copies used for mutations)")
    print(f"   Session DB dir: {SESSION_DB_DIR}")
    
    print(f"\n🚀 Starting Retail MCP Server...")
    print(f"   Transport: {args.transport}")
    if args.transport == "sse":
        print(f"   Host: {args.host}")
        print(f"   Port: {args.port}")
        print(f"   SSE endpoint: http://{args.host}:{args.port}/sse")
    
    # Run the server
    mcp.run(transport=args.transport, host=args.host, port=args.port)
