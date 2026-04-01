#!/usr/bin/env python3
"""
MCP Server for Banking Card-Management Tools - Fully Standalone

All business logic is directly in the MCP tools - no intermediate wrapper classes.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, cast

from fastmcp import FastMCP

from banking_data_model import (
    BankingDB,
    BlockReason,
    Card,
    CardEvent,
    CardLimitBounds,
    CardLimits,
    Customer,
    CustomerAddress,
    CustomerName,
)
from error_hints import analyze_execution_error


DEFAULT_DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "banking" / "db.json")
ALLOWED_BLOCK_REASONS = {"lost", "stolen", "suspected_fraud", "customer_request"}


def ensure_db(db_path: str) -> None:
    """Check that the banking database exists; exit with instructions if missing."""
    if Path(db_path).exists():
        return
    print(f"\n❌ Database not found: {db_path}")
    print(f"   The banking database is included in the repository.")
    print(f"   Make sure the data/ directory is present (e.g. git checkout).")
    sys.exit(1)


mcp = FastMCP(
    "Banking Tools Server",
    instructions="""You are a banking card-management support agent. Use these tools to help customers with:
- Authenticating their profile by email or name + date of birth
- Reviewing their cards and current card-control limits
- Changing supported daily card limits within allowed bounds
- Freezing and unfreezing cards
- Permanently blocking cards for lost/stolen/fraud/customer-request reasons

Always verify the customer's identity before revealing card details or making changes. Ask for explicit confirmation before any mutation.""",
)

_db: Optional[BankingDB] = None
_original_db_path: str = ""
_session_dbs: Dict[str, BankingDB] = {}
SESSION_DB_DIR = Path(__file__).parent / "session_dbs"
SESSION_DB_DIR.mkdir(exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _session_db_file(session_id: str) -> Path:
    safe = "".join(ch for ch in session_id if ch.isalnum() or ch in ("-", "_"))
    if not safe:
        safe = "session"
    return SESSION_DB_DIR / f"banking_{safe[:64]}.json"


def get_db(session_id: str = "") -> BankingDB:
    """Get the database for a given session."""
    global _db, _original_db_path

    if _db is None:
        db_path = os.environ.get("BANKING_DB_PATH", DEFAULT_DB_PATH)
        _original_db_path = db_path
        _db = BankingDB.load(db_path)
        _db._db_path = ""
        print(f"Loaded template banking database from {db_path}")
        print(f"  - {len(_db.customers)} customers")
        print(f"  - {len(_db.cards)} cards")

    if not session_id:
        return _db

    if session_id not in _session_dbs:
        db = BankingDB.load(_original_db_path)
        db._db_path = str(_session_db_file(session_id))
        _session_dbs[session_id] = db
        print(f"🆕 Created pristine banking DB for session {session_id[:8]}... ({len(_session_dbs)} active sessions)")

    return _session_dbs[session_id]


def _save_db(db: BankingDB) -> None:
    db.meta["updated_at"] = _now_iso()
    db.save()


def _require_customer(db: BankingDB, customer_id: str) -> Customer:
    customer = db.customers.get(customer_id)
    if not customer:
        raise ValueError("Customer not found")
    return customer


def _require_card(db: BankingDB, customer_id: str, card_id: str) -> Card:
    customer = _require_customer(db, customer_id)
    if card_id not in customer.cards:
        raise ValueError("Card does not belong to customer")

    card = db.cards.get(card_id)
    if not card:
        raise ValueError("Card not found")
    return card


def _append_event(card: Card, action: str, details: Dict[str, Any]) -> None:
    card.events.append(
        CardEvent(
            timestamp=_now_iso(),
            action=action,
            details=details,
        )
    )


def _card_summary(card: Card) -> Dict[str, Any]:
    return {
        "card_id": card.card_id,
        "nickname": card.nickname,
        "product_name": card.product_name,
        "card_type": card.card_type,
        "network": card.network,
        "last_four": card.last_four,
        "status": card.status,
        "linked_account": card.linked_account,
        "limits": card.limits.model_dump(),
        "limit_bounds": card.limit_bounds.model_dump(),
        "temporary_block_reason": card.temporary_block_reason,
        "block_reason": card.block_reason,
    }


def _get_data_model_defs() -> Dict[str, dict]:
    model_classes = [
        CustomerName,
        CustomerAddress,
        CardLimits,
        CardLimitBounds,
        CardEvent,
        Card,
        Customer,
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
        "find_customer_id_by_email",
        "find_customer_id_by_name_dob",
        "get_customer_profile",
        "list_customer_cards",
        "find_card_id_by_last_four",
        "get_card_details",
        "update_card_limits",
        "freeze_card",
        "unfreeze_card",
        "block_card",
        "transfer_to_human_agents",
    ]

    return {
        "ordered_actions": ordered_actions,
        "return_types": {
            "calculate": "str",
            "find_customer_id_by_email": "str",
            "find_customer_id_by_name_dob": "str",
            "get_customer_profile": "str (JSON)",
            "list_customer_cards": "str (JSON)",
            "find_card_id_by_last_four": "str",
            "get_card_details": "str (JSON)",
            "update_card_limits": "str (JSON)",
            "freeze_card": "str (JSON)",
            "unfreeze_card": "str (JSON)",
            "block_card": "str (JSON)",
            "transfer_to_human_agents": "str",
        },
        "semantic_types": {
            "get_customer_profile": "Customer",
            "list_customer_cards": "dict[card_id, CardSummary]",
            "get_card_details": "Card",
            "update_card_limits": "Card",
            "freeze_card": "Card",
            "unfreeze_card": "Card",
            "block_card": "Card",
        },
        "data_model_defs": _get_data_model_defs(),
    }


@mcp.tool()
def find_customer_id_by_email(email: str, session_id: str = "") -> str:
    """Find customer id by email. Use this first to identify a customer.

    Args:
        email: Customer email such as 'emma.reed@examplebank.com'.

    Returns:
        The customer id if found.
    """
    db = get_db(session_id)
    for customer_id, customer in db.customers.items():
        if customer.email.lower() == email.lower():
            return customer_id
    raise ValueError("Customer not found")


@mcp.tool()
def find_customer_id_by_name_dob(first_name: str, last_name: str, date_of_birth: str, session_id: str = "") -> str:
    """Find customer id by first name, last name, and date of birth.

    Args:
        first_name: Customer first name.
        last_name: Customer last name.
        date_of_birth: Date of birth in YYYY-MM-DD format.

    Returns:
        The customer id if found.
    """
    db = get_db(session_id)
    for customer_id, customer in db.customers.items():
        if (
            customer.name.first_name.lower() == first_name.lower()
            and customer.name.last_name.lower() == last_name.lower()
            and customer.date_of_birth == date_of_birth
        ):
            return customer_id
    raise ValueError("Customer not found")


@mcp.tool()
def get_customer_profile(customer_id: str, session_id: str = "") -> str:
    """Get customer profile information.

    Args:
        customer_id: Authenticated customer id.

    Returns:
        A JSON STRING customer object.
    """
    db = get_db(session_id)
    customer = _require_customer(db, customer_id)
    return customer.model_dump_json(indent=2)


@mcp.tool()
def list_customer_cards(customer_id: str, session_id: str = "") -> str:
    """List all cards for an authenticated customer.

    Args:
        customer_id: Authenticated customer id.

    Returns:
        A JSON STRING dictionary keyed by card_id.
    """
    db = get_db(session_id)
    customer = _require_customer(db, customer_id)
    payload = {
        card_id: _card_summary(db.cards[card_id])
        for card_id in customer.cards
        if card_id in db.cards
    }
    return json.dumps(payload, indent=2)


@mcp.tool()
def find_card_id_by_last_four(customer_id: str, last_four: str, session_id: str = "") -> str:
    """Find a customer's card id by the last four digits.

    Args:
        customer_id: Authenticated customer id.
        last_four: Last four digits of the card.

    Returns:
        Matching card id.
    """
    db = get_db(session_id)
    customer = _require_customer(db, customer_id)
    for card_id in customer.cards:
        card = db.cards.get(card_id)
        if card and card.last_four == last_four:
            return card_id
    raise ValueError("Card not found")


@mcp.tool()
def get_card_details(customer_id: str, card_id: str, session_id: str = "") -> str:
    """Get detailed information for one of the customer's cards.

    Args:
        customer_id: Authenticated customer id.
        card_id: Card id to inspect.

    Returns:
        A JSON STRING card object.
    """
    db = get_db(session_id)
    card = _require_card(db, customer_id, card_id)
    return card.model_dump_json(indent=2)


@mcp.tool()
def calculate(expression: str, session_id: str = "") -> str:
    """Calculate the result of a mathematical expression.

    Args:
        expression: Expression such as '2500 - 1500'.

    Returns:
        The calculated result as a string.
    """
    if not all(char in "0123456789+-*/(). " for char in expression):
        raise ValueError("Invalid characters in expression")
    return str(round(float(eval(expression, {"__builtins__": None}, {})), 6))


@mcp.tool()
def transfer_to_human_agents(summary: str, session_id: str = "") -> str:
    """Transfer the customer to a human agent.

    Returns:
        Confirmation message.
    """
    return "Transfer successful"


@mcp.tool()
def get_execution_error_hint(error_msg: str, code: str = "", session_id: str = "") -> str:
    """Return a recovery hint for sandbox execution/tool errors."""
    return analyze_execution_error(error_msg=error_msg, code=code, domain="banking")


@mcp.tool()
def get_tool_metadata(session_id: str = "") -> str:
    """Return metadata used to build execute_python action/data-model description."""
    return json.dumps(_get_tool_metadata_payload())


@mcp.tool()
def update_card_limits(
    customer_id: str,
    card_id: str,
    atm_withdrawal_limit: Optional[int] = None,
    pos_purchase_limit: Optional[int] = None,
    ecommerce_purchase_limit: Optional[int] = None,
    contactless_purchase_limit: Optional[int] = None,
    session_id: str = "",
) -> str:
    """Update one or more daily card limits within the allowed bounds.

    Ask for explicit user confirmation before making changes.

    Returns:
        A JSON STRING card object.
    """
    db = get_db(session_id)
    card = _require_card(db, customer_id, card_id)

    if card.status == "blocked":
        raise ValueError("Blocked cards cannot have limits changed")

    requested_updates = {
        "atm_withdrawal_limit": atm_withdrawal_limit,
        "pos_purchase_limit": pos_purchase_limit,
        "ecommerce_purchase_limit": ecommerce_purchase_limit,
        "contactless_purchase_limit": contactless_purchase_limit,
    }
    changes = {key: value for key, value in requested_updates.items() if value is not None}
    if not changes:
        raise ValueError("At least one limit value must be provided")

    old_limits = card.limits.model_dump()
    new_limits = card.limits.model_dump()

    for field_name, new_value in changes.items():
        minimum = getattr(card.limit_bounds.minimum, field_name)
        maximum = getattr(card.limit_bounds.maximum, field_name)
        if int(new_value) < minimum or int(new_value) > maximum:
            raise ValueError(
                f"{field_name} must be between {minimum} and {maximum}"
            )
        setattr(card.limits, field_name, int(new_value))
        new_limits[field_name] = int(new_value)

    _append_event(
        card,
        "limits_updated",
        {
            "old_limits": old_limits,
            "new_limits": new_limits,
        },
    )
    _save_db(db)
    return card.model_dump_json(indent=2)


@mcp.tool()
def freeze_card(customer_id: str, card_id: str, reason: str, session_id: str = "") -> str:
    """Temporarily freeze a card.

    Ask for explicit user confirmation before freezing the card.

    Args:
        reason: Non-empty customer-provided reason for the temporary freeze.

    Returns:
        A JSON STRING card object.
    """
    db = get_db(session_id)
    card = _require_card(db, customer_id, card_id)

    clean_reason = reason.strip()
    if not clean_reason:
        raise ValueError("Freeze reason is required")
    if card.status == "blocked":
        raise ValueError("Blocked cards cannot be frozen")
    if card.status == "frozen":
        raise ValueError("Card is already frozen")

    card.status = "frozen"
    card.temporary_block_reason = clean_reason
    _append_event(
        card,
        "card_frozen",
        {"reason": clean_reason},
    )
    _save_db(db)
    return card.model_dump_json(indent=2)


@mcp.tool()
def unfreeze_card(customer_id: str, card_id: str, session_id: str = "") -> str:
    """Remove a temporary freeze from a card.

    Ask for explicit user confirmation before unfreezing the card.

    Returns:
        A JSON STRING card object.
    """
    db = get_db(session_id)
    card = _require_card(db, customer_id, card_id)

    if card.status != "frozen":
        raise ValueError("Only frozen cards can be unfrozen")

    previous_reason = card.temporary_block_reason
    card.status = "active"
    card.temporary_block_reason = None
    _append_event(
        card,
        "card_unfrozen",
        {"previous_reason": previous_reason},
    )
    _save_db(db)
    return card.model_dump_json(indent=2)


@mcp.tool()
def block_card(customer_id: str, card_id: str, reason: str, session_id: str = "") -> str:
    """Permanently block a card.

    Ask for explicit user confirmation before blocking the card.

    Args:
        reason: One of 'lost', 'stolen', 'suspected_fraud', or 'customer_request'.

    Returns:
        A JSON STRING card object.
    """
    db = get_db(session_id)
    card = _require_card(db, customer_id, card_id)

    normalized_reason = reason.strip().lower().replace(" ", "_").replace("-", "_")
    if normalized_reason not in ALLOWED_BLOCK_REASONS:
        raise ValueError(
            "Block reason must be one of: lost, stolen, suspected_fraud, customer_request"
        )
    if card.status == "blocked":
        raise ValueError("Card is already blocked")

    card.status = "blocked"
    card.temporary_block_reason = None
    card.block_reason = cast(BlockReason, normalized_reason)
    _append_event(
        card,
        "card_blocked",
        {"reason": normalized_reason},
    )
    _save_db(db)
    return card.model_dump_json(indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Banking MCP Server")
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help="Path to the banking database JSON file",
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
    os.environ["BANKING_DB_PATH"] = args.db_path

    ensure_db(args.db_path)
    get_db()
    print("   Original DB file is READ-ONLY (per-session copies used for mutations)")
    print(f"   Session DB dir: {SESSION_DB_DIR}")

    print("\n🚀 Starting Banking MCP Server...")
    print(f"   Transport: {args.transport}")
    if args.transport == "sse":
        print(f"   Host: {args.host}")
        print(f"   Port: {args.port}")
        print(f"   SSE endpoint: http://{args.host}:{args.port}/sse")

    mcp.run(transport=args.transport, host=args.host, port=args.port)
