#!/usr/bin/env python3
"""
MCP Server for Demo Stocks Tools - Fully Standalone

All business logic is directly in the MCP tools - no intermediate wrapper classes.
"""

import argparse
import json
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

# Add parent directory to sys.path for shared modules (error_hints)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from error_hints import analyze_execution_error
from stocks_data_model import StocksDB


DEFAULT_DB_PATH = str(Path(__file__).resolve().parent / "data" / "db.json")


def ensure_db(db_path: str) -> None:
    """Check that the stocks database exists; exit with instructions if missing."""
    if Path(db_path).exists():
        return
    print(f"\n❌ Database not found: {db_path}")
    print(f"   The stocks database is included in the repository.")
    print(f"   Make sure the data/ directory is present (e.g. git checkout).")
    sys.exit(1)


mcp = FastMCP(
    "Stocks Tools Server",
    instructions="""You are a stock trading support agent. Use these tools to help users with:
- Looking up account and portfolio details
- Retrieving market quotes and symbol lists
- Placing/cancelling market and limit orders
- Reviewing order history and account balances

Always verify account identity before any trade. Ask for explicit confirmation before placing or cancelling orders.""",
)


_db: Optional[Dict[str, Any]] = None
_original_db_path: str = ""
_session_dbs: Dict[str, Dict[str, Any]] = {}
SESSION_DB_DIR = Path(__file__).resolve().parent.parent / "session_dbs"
SESSION_DB_DIR.mkdir(exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _session_db_file(session_id: str) -> Path:
    safe = "".join(ch for ch in session_id if ch.isalnum() or ch in ("-", "_"))
    if not safe:
        safe = "session"
    return SESSION_DB_DIR / f"stocks_{safe[:64]}.json"


def _load_db(path: str) -> Dict[str, Any]:
    db = StocksDB.load(path)
    return db.model_dump(mode="python")


def _save_db(db: Dict[str, Any]) -> None:
    db_path = db.get("_db_path", "")
    if db_path:
        persist = {k: v for k, v in db.items() if k != "_db_path"}
        validated_db = StocksDB.model_validate(persist)
        validated_db._db_path = db_path
        validated_db.save()


def get_db(session_id: str = "") -> Dict[str, Any]:
    global _db, _original_db_path

    if _db is None:
        db_path = os.environ.get("STOCKS_DB_PATH", DEFAULT_DB_PATH)
        _original_db_path = db_path
        _db = _load_db(db_path)
        _db["_db_path"] = ""
        print(f"Loaded template stocks database from {db_path}")
        print(f"  - {len(_db.get('accounts', {}))} accounts")
        print(f"  - {len(_db.get('market', {}))} symbols")
        print(f"  - {len(_db.get('orders', {}))} orders")

    if not session_id:
        return _db

    if session_id not in _session_dbs:
        db = _load_db(_original_db_path)
        db["_db_path"] = str(_session_db_file(session_id))
        _session_dbs[session_id] = db
        print(f"🆕 Created pristine stocks DB for session {session_id[:8]}... ({len(_session_dbs)} active sessions)")

    return _session_dbs[session_id]


def _normalize_symbol(symbol: str, db: Dict[str, Any]) -> str:
    sym = symbol.strip().upper()
    if sym not in db.get("market", {}):
        raise ValueError(f"Symbol not found: {sym}")
    return sym


def _require_account(db: Dict[str, Any], account_id: str) -> Dict[str, Any]:
    account = db.get("accounts", {}).get(account_id)
    if not account:
        raise ValueError("Account not found")
    return account


def _next_order_id(db: Dict[str, Any]) -> str:
    next_id = int(db.get("meta", {}).get("next_order_id", 1))
    order_id = f"ORD-{next_id:06d}"
    db.setdefault("meta", {})["next_order_id"] = next_id + 1
    return order_id


def _account_snapshot(account: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "account_id": account["account_id"],
        "name": account["name"],
        "email": account["email"],
        "cash_balance": round(float(account["cash_balance"]), 2),
        "positions": account.get("positions", {}),
        "watchlist": account.get("watchlist", []),
        "order_ids": account.get("order_ids", []),
    }


def _market_price(db: Dict[str, Any], symbol: str) -> float:
    return float(db["market"][symbol]["current_price"])


def _ensure_quantity(quantity: int) -> int:
    if quantity <= 0:
        raise ValueError("Quantity must be greater than 0")
    return int(quantity)


def _ensure_limit_price(limit_price: float) -> float:
    if limit_price <= 0:
        raise ValueError("limit_price must be greater than 0")
    return round(float(limit_price), 2)


def _apply_buy_fill(account: Dict[str, Any], symbol: str, quantity: int, price: float) -> None:
    total_cost = round(quantity * price, 2)
    if float(account["cash_balance"]) < total_cost:
        raise ValueError("Insufficient cash balance")

    positions = account.setdefault("positions", {})
    existing = positions.get(symbol)
    if existing:
        old_qty = int(existing["quantity"])
        old_avg = float(existing["avg_cost"])
        new_qty = old_qty + quantity
        new_avg = ((old_qty * old_avg) + (quantity * price)) / new_qty
        positions[symbol] = {"quantity": new_qty, "avg_cost": round(new_avg, 4)}
    else:
        positions[symbol] = {"quantity": quantity, "avg_cost": round(price, 4)}

    account["cash_balance"] = round(float(account["cash_balance"]) - total_cost, 2)


def _apply_sell_fill(account: Dict[str, Any], symbol: str, quantity: int, price: float) -> None:
    positions = account.setdefault("positions", {})
    existing = positions.get(symbol)
    if not existing or int(existing["quantity"]) < quantity:
        raise ValueError("Insufficient shares to sell")

    existing["quantity"] = int(existing["quantity"]) - quantity
    if existing["quantity"] == 0:
        del positions[symbol]

    proceeds = round(quantity * price, 2)
    account["cash_balance"] = round(float(account["cash_balance"]) + proceeds, 2)


def _create_order(
    db: Dict[str, Any],
    account: Dict[str, Any],
    symbol: str,
    side: str,
    order_type: str,
    quantity: int,
    limit_price: Optional[float],
    status: str,
    executed_price: Optional[float],
) -> Dict[str, Any]:
    order_id = _next_order_id(db)
    now = _now_iso()
    order = {
        "order_id": order_id,
        "account_id": account["account_id"],
        "symbol": symbol,
        "side": side,
        "order_type": order_type,
        "quantity": quantity,
        "limit_price": limit_price,
        "status": status,
        "executed_price": executed_price,
        "created_at": now,
        "filled_at": now if status == "filled" else None,
    }
    db.setdefault("orders", {})[order_id] = order
    account.setdefault("order_ids", []).append(order_id)
    db.setdefault("meta", {})["updated_at"] = now
    return order


def _get_data_model_defs() -> Dict[str, dict]:
    return {
        "Position": {
            "description": "Current holdings for a symbol",
            "properties": {
                "quantity": {"type": "integer"},
                "avg_cost": {"type": "number"},
            },
        },
        "Account": {
            "description": "Trading account profile",
            "properties": {
                "account_id": {"type": "string"},
                "name": {"type": "string"},
                "email": {"type": "string"},
                "cash_balance": {"type": "number"},
                "positions": {"type": "object"},
                "watchlist": {"type": "array"},
                "order_ids": {"type": "array"},
            },
        },
        "Quote": {
            "description": "Current market quote",
            "properties": {
                "symbol": {"type": "string"},
                "name": {"type": "string"},
                "sector": {"type": "string"},
                "current_price": {"type": "number"},
                "day_open": {"type": "number"},
                "day_high": {"type": "number"},
                "day_low": {"type": "number"},
                "volume": {"type": "integer"},
            },
        },
        "Order": {
            "description": "Trade order record",
            "properties": {
                "order_id": {"type": "string"},
                "account_id": {"type": "string"},
                "symbol": {"type": "string"},
                "side": {"type": "string"},
                "order_type": {"type": "string"},
                "quantity": {"type": "integer"},
                "limit_price": {"type": "number"},
                "status": {"type": "string"},
                "executed_price": {"type": "number"},
                "created_at": {"type": "string"},
                "filled_at": {"type": "string"},
            },
        },
        "Mover": {
            "description": "Simple market mover snapshot",
            "properties": {
                "symbol": {"type": "string"},
                "name": {"type": "string"},
                "percent_change": {"type": "number"},
                "current_price": {"type": "number"},
            },
        },
    }


def _get_tool_metadata_payload() -> Dict[str, Any]:
    ordered_actions = [
        "calculate",
        "find_account_id_by_email",
        "get_account_summary",
        "get_portfolio",
        "get_quote",
        "list_available_symbols",
        "list_market_movers",
        "get_order_history",
        "place_market_buy",
        "place_market_sell",
        "place_limit_buy",
        "place_limit_sell",
        "cancel_open_order",
        "transfer_to_human_agents",
    ]

    return {
        "ordered_actions": ordered_actions,
        "return_types": {
            "calculate": "str",
            "find_account_id_by_email": "str",
            "get_account_summary": "str (JSON)",
            "get_portfolio": "str (JSON)",
            "get_quote": "str (JSON)",
            "list_available_symbols": "str (JSON)",
            "list_market_movers": "str (JSON)",
            "get_order_history": "str (JSON)",
            "place_market_buy": "str (JSON)",
            "place_market_sell": "str (JSON)",
            "place_limit_buy": "str (JSON)",
            "place_limit_sell": "str (JSON)",
            "cancel_open_order": "str (JSON)",
            "transfer_to_human_agents": "str",
        },
        "semantic_types": {
            "get_account_summary": "Account",
            "get_portfolio": "dict[symbol, Position]",
            "get_quote": "Quote",
            "list_available_symbols": "dict[symbol, name]",
            "list_market_movers": "list[Mover]",
            "get_order_history": "list[Order]",
            "place_market_buy": "Order",
            "place_market_sell": "Order",
            "place_limit_buy": "Order",
            "place_limit_sell": "Order",
            "cancel_open_order": "Order",
        },
        "data_model_defs": _get_data_model_defs(),
    }


@mcp.tool()
def find_account_id_by_email(email: str, session_id: str = "") -> str:
    """Find account id by email. Use this first to identify a customer.

    Args:
        email: Account email, such as 'jane.miller@example.com'.

    Returns:
        The account id if found.
    """
    db = get_db(session_id)
    for account_id, account in db.get("accounts", {}).items():
        if account.get("email", "").lower() == email.lower():
            return account_id
    raise ValueError("Account not found")


@mcp.tool()
def get_account_summary(account_id: str, session_id: str = "") -> str:
    """Get account profile summary including cash balance and watchlist.

    Args:
        account_id: The trading account id.

    Returns:
        A JSON STRING (not a dict). You MUST parse it: account = json.loads(result)
    """
    db = get_db(session_id)
    account = _require_account(db, account_id)
    return json.dumps(_account_snapshot(account), indent=2)


@mcp.tool()
def get_portfolio(account_id: str, session_id: str = "") -> str:
    """Get current portfolio positions for an account.

    Args:
        account_id: The trading account id.

    Returns:
        A JSON STRING of positions keyed by symbol.
    """
    db = get_db(session_id)
    account = _require_account(db, account_id)
    return json.dumps(account.get("positions", {}), indent=2)


@mcp.tool()
def get_quote(symbol: str, session_id: str = "") -> str:
    """Get current market quote for a stock symbol.

    Args:
        symbol: Stock ticker symbol, such as 'AAPL'.

    Returns:
        A JSON STRING with quote fields.
    """
    db = get_db(session_id)
    sym = _normalize_symbol(symbol, db)
    return json.dumps(db["market"][sym], indent=2)


@mcp.tool()
def list_available_symbols(session_id: str = "") -> str:
    """List all available symbols in the demo market.

    Returns:
        A JSON STRING dictionary of {symbol: company_name}.
    """
    db = get_db(session_id)
    result = {
        symbol: info.get("name", symbol)
        for symbol, info in sorted(db.get("market", {}).items())
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def list_market_movers(top_n: int = 5, session_id: str = "") -> str:
    """List top movers by absolute percent change from day open.

    Args:
        top_n: Maximum number of movers to return.

    Returns:
        A JSON STRING list of mover objects.
    """
    db = get_db(session_id)
    movers = []
    for symbol, quote in db.get("market", {}).items():
        day_open = float(quote["day_open"])
        current = float(quote["current_price"])
        pct = ((current - day_open) / day_open) * 100 if day_open else 0.0
        movers.append(
            {
                "symbol": symbol,
                "name": quote.get("name", symbol),
                "percent_change": round(pct, 4),
                "current_price": current,
            }
        )

    movers.sort(key=lambda item: abs(item["percent_change"]), reverse=True)
    return json.dumps(movers[: max(1, top_n)], indent=2)


@mcp.tool()
def get_order_history(account_id: str, limit: int = 20, session_id: str = "") -> str:
    """Get recent order history for an account.

    Args:
        account_id: Trading account id.
        limit: Maximum number of orders to return.

    Returns:
        A JSON STRING list of orders, newest first.
    """
    db = get_db(session_id)
    account = _require_account(db, account_id)
    all_orders = db.get("orders", {})
    order_ids = list(account.get("order_ids", []))
    order_ids.sort(reverse=True)

    history = [all_orders[order_id] for order_id in order_ids if order_id in all_orders]
    return json.dumps(history[: max(1, limit)], indent=2)


@mcp.tool()
def calculate(expression: str, session_id: str = "") -> str:
    """Calculate the result of a mathematical expression.

    Args:
        expression: Expression such as '10000 * 0.05'.

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
    return analyze_execution_error(error_msg=error_msg, code=code, domain="stocks")


@mcp.tool()
def get_tool_metadata(session_id: str = "") -> str:
    """Return metadata used to build execute_python action/data-model description."""
    return json.dumps(_get_tool_metadata_payload())


@mcp.tool()
def place_market_buy(account_id: str, symbol: str, quantity: int, session_id: str = "") -> str:
    """Place a market buy order and execute immediately at current price.

    Ask for explicit user confirmation before placing the order.

    Args:
        account_id: Trading account id.
        symbol: Ticker symbol such as 'AAPL'.
        quantity: Number of shares to buy.

    Returns:
        A JSON STRING order object.
    """
    db = get_db(session_id)
    account = _require_account(db, account_id)
    sym = _normalize_symbol(symbol, db)
    qty = _ensure_quantity(quantity)
    price = _market_price(db, sym)

    _apply_buy_fill(account, sym, qty, price)
    order = _create_order(
        db,
        account,
        symbol=sym,
        side="buy",
        order_type="market",
        quantity=qty,
        limit_price=None,
        status="filled",
        executed_price=price,
    )

    _save_db(db)
    return json.dumps(order, indent=2)


@mcp.tool()
def place_market_sell(account_id: str, symbol: str, quantity: int, session_id: str = "") -> str:
    """Place a market sell order and execute immediately at current price.

    Ask for explicit user confirmation before placing the order.

    Args:
        account_id: Trading account id.
        symbol: Ticker symbol such as 'AAPL'.
        quantity: Number of shares to sell.

    Returns:
        A JSON STRING order object.
    """
    db = get_db(session_id)
    account = _require_account(db, account_id)
    sym = _normalize_symbol(symbol, db)
    qty = _ensure_quantity(quantity)
    price = _market_price(db, sym)

    _apply_sell_fill(account, sym, qty, price)
    order = _create_order(
        db,
        account,
        symbol=sym,
        side="sell",
        order_type="market",
        quantity=qty,
        limit_price=None,
        status="filled",
        executed_price=price,
    )

    _save_db(db)
    return json.dumps(order, indent=2)


@mcp.tool()
def place_limit_buy(
    account_id: str,
    symbol: str,
    quantity: int,
    limit_price: float,
    session_id: str = "",
) -> str:
    """Place a limit buy order.

    If current price <= limit_price, order is filled immediately; otherwise stays open.
    Ask for explicit user confirmation before placing the order.

    Returns:
        A JSON STRING order object.
    """
    db = get_db(session_id)
    account = _require_account(db, account_id)
    sym = _normalize_symbol(symbol, db)
    qty = _ensure_quantity(quantity)
    limit_px = _ensure_limit_price(limit_price)
    current = _market_price(db, sym)

    status = "open"
    executed_price: Optional[float] = None
    if current <= limit_px:
        _apply_buy_fill(account, sym, qty, current)
        status = "filled"
        executed_price = current

    order = _create_order(
        db,
        account,
        symbol=sym,
        side="buy",
        order_type="limit",
        quantity=qty,
        limit_price=limit_px,
        status=status,
        executed_price=executed_price,
    )

    _save_db(db)
    return json.dumps(order, indent=2)


@mcp.tool()
def place_limit_sell(
    account_id: str,
    symbol: str,
    quantity: int,
    limit_price: float,
    session_id: str = "",
) -> str:
    """Place a limit sell order.

    If current price >= limit_price, order is filled immediately; otherwise stays open.
    Ask for explicit user confirmation before placing the order.

    Returns:
        A JSON STRING order object.
    """
    db = get_db(session_id)
    account = _require_account(db, account_id)
    sym = _normalize_symbol(symbol, db)
    qty = _ensure_quantity(quantity)
    limit_px = _ensure_limit_price(limit_price)
    current = _market_price(db, sym)

    positions = account.setdefault("positions", {})
    existing = positions.get(sym)
    if not existing or int(existing.get("quantity", 0)) < qty:
        raise ValueError("Insufficient shares to place sell order")

    status = "open"
    executed_price: Optional[float] = None
    if current >= limit_px:
        _apply_sell_fill(account, sym, qty, current)
        status = "filled"
        executed_price = current

    order = _create_order(
        db,
        account,
        symbol=sym,
        side="sell",
        order_type="limit",
        quantity=qty,
        limit_price=limit_px,
        status=status,
        executed_price=executed_price,
    )

    _save_db(db)
    return json.dumps(order, indent=2)


@mcp.tool()
def cancel_open_order(account_id: str, order_id: str, session_id: str = "") -> str:
    """Cancel an open order.

    Ask for explicit user confirmation before cancellation.

    Args:
        account_id: Trading account id.
        order_id: Order ID such as 'ORD-000004'.

    Returns:
        A JSON STRING order object.
    """
    db = get_db(session_id)
    _require_account(db, account_id)

    order = db.get("orders", {}).get(order_id)
    if not order:
        raise ValueError("Order not found")
    if order.get("account_id") != account_id:
        raise ValueError("Order does not belong to account")
    if order.get("status") != "open":
        raise ValueError("Only open orders can be cancelled")

    order["status"] = "cancelled"
    db.setdefault("meta", {})["updated_at"] = _now_iso()
    _save_db(db)
    return json.dumps(order, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stocks MCP Server")
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help="Path to the stocks database JSON file",
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
    os.environ["STOCKS_DB_PATH"] = args.db_path

    ensure_db(args.db_path)
    get_db()
    print("   Original DB file is READ-ONLY (per-session copies used for mutations)")
    print(f"   Session DB dir: {SESSION_DB_DIR}")

    print("\n🚀 Starting Stocks MCP Server...")
    print(f"   Transport: {args.transport}")
    if args.transport == "sse":
        print(f"   Host: {args.host}")
        print(f"   Port: {args.port}")
        print(f"   SSE endpoint: http://{args.host}:{args.port}/sse")

    mcp.run(transport=args.transport, host=args.host, port=args.port)
