#!/usr/bin/env python3
"""
MCP Server for Airline Tools - Fully Standalone

All business logic is directly in the MCP tools - no intermediate wrapper classes.
"""

import argparse
import json
import os
import sys
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

# Add parent directory to sys.path for shared modules (error_hints)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from airline_data_model import (
    AirportCode,
    CabinClass,
    Certificate,
    DirectFlight,
    FlightDB,
    FlightDateStatusAvailable,
    FlightInfo,
    Insurance,
    Passenger,
    Payment,
    Reservation,
    ReservationFlight,
    User,
)
from error_hints import analyze_execution_error


DEFAULT_DB_PATH = str(Path(__file__).resolve().parent / "data" / "db.json")

TAU2_BENCH_URL = (
    "https://raw.githubusercontent.com/sierra-research/tau2-bench/"
    "main/data/tau2/domains/airline/db.json"
)


def ensure_db(db_path: str) -> None:
    """Check that the airline database exists; auto-download from tau2-bench if missing."""
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


mcp = FastMCP(
    "Airline Tools Server",
    instructions="""You are an airline customer service agent. Use these tools to help customers with:
- Looking up users and reservation details
- Searching direct and one-stop flight options
- Booking, updating, and cancelling reservations
- Managing baggage and passenger details
- Checking flight status

Always verify identity and reservation details before making changes. Ask for confirmation before mutations.""",
)


# Global database state
_db: Optional[FlightDB] = None  # Read-only template DB
_original_db_path: str = ""  # Path to original pristine DB file
_session_dbs: Dict[str, FlightDB] = {}  # Per-session DB copies
SESSION_DB_DIR = Path(__file__).resolve().parent.parent / "session_dbs"
SESSION_DB_DIR.mkdir(exist_ok=True)


def get_db(session_id: str = "") -> FlightDB:
    """Get the database for a given session.

    If session_id is empty, returns the read-only template DB.
    If session_id is provided, returns a per-session pristine copy
    (created on first access from the original file).
    """
    global _db, _original_db_path

    if _db is None:
        db_path = os.environ.get("AIRLINE_DB_PATH", DEFAULT_DB_PATH)
        _original_db_path = db_path
        _db = FlightDB.load(db_path)
        _db._db_path = ""  # Prevent accidental writes to original file
        print(f"Loaded template airline database from {db_path}")
        print(f"  - {len(_db.flights)} flights")
        print(f"  - {len(_db.users)} users")
        print(f"  - {len(_db.reservations)} reservations")

    if not session_id:
        return _db

    if session_id not in _session_dbs:
        db = FlightDB.load(_original_db_path)
        session_db_file = SESSION_DB_DIR / f"{session_id[:32]}.json"
        db._db_path = str(session_db_file)
        _session_dbs[session_id] = db
        print(
            f"🆕 Created pristine airline DB for session {session_id[:8]}... "
            f"({len(_session_dbs)} active sessions)"
        )

    return _session_dbs[session_id]


def _serialize(value):
    if hasattr(value, "model_dump_json"):
        return value.model_dump_json(indent=2)
    if isinstance(value, list):
        normalized = []
        for item in value:
            if hasattr(item, "model_dump"):
                normalized.append(item.model_dump(mode="json"))
            elif isinstance(item, list):
                normalized.append(
                    [
                        sub.model_dump(mode="json") if hasattr(sub, "model_dump") else sub
                        for sub in item
                    ]
                )
            else:
                normalized.append(item)
        return json.dumps(normalized, indent=2)
    return value


def _get_user(db: FlightDB, user_id: str):
    if user_id not in db.users:
        raise ValueError(f"User {user_id} not found")
    return db.users[user_id]


def _get_reservation(db: FlightDB, reservation_id: str):
    if reservation_id not in db.reservations:
        raise ValueError(f"Reservation {reservation_id} not found")
    return db.reservations[reservation_id]


def _get_flight(db: FlightDB, flight_number: str):
    if flight_number not in db.flights:
        raise ValueError(f"Flight {flight_number} not found")
    return db.flights[flight_number]


def _get_flight_instance(db: FlightDB, flight_number: str, date: str):
    flight = _get_flight(db, flight_number)
    if date not in flight.dates:
        raise ValueError(f"Flight {flight_number} not found on date {date}")
    return flight.dates[date]


def _get_flights_from_flight_infos(db: FlightDB, flight_infos: List[FlightInfo]) -> list:
    flights = []
    for flight_info in flight_infos:
        flights.append(_get_flight_instance(db, flight_info.flight_number, flight_info.date))
    return flights


def _get_new_reservation_id(db: FlightDB) -> str:
    for reservation_id in ["HATHAT", "HATHAU", "HATHAV"]:
        if reservation_id not in db.reservations:
            return reservation_id
    raise ValueError("Too many reservations")


def _get_new_payment_id() -> List[int]:
    return [3221322, 3221323, 3221324]


def _get_datetime() -> str:
    return "2024-05-15T15:00:00"


def _search_direct_flight(
    db: FlightDB,
    date: str,
    origin: Optional[str] = None,
    destination: Optional[str] = None,
    leave_after: Optional[str] = None,
) -> list[DirectFlight]:
    results = []
    for flight in db.flights.values():
        check = (
            (origin is None or flight.origin == origin)
            and (destination is None or flight.destination == destination)
            and (date in flight.dates)
            and (flight.dates[date].status == "available")
            and (
                leave_after is None
                or flight.scheduled_departure_time_est >= leave_after
            )
        )
        if check:
            direct_flight = DirectFlight(
                flight_number=flight.flight_number,
                origin=flight.origin,
                destination=flight.destination,
                status="available",
                scheduled_departure_time_est=flight.scheduled_departure_time_est,
                scheduled_arrival_time_est=flight.scheduled_arrival_time_est,
                available_seats=flight.dates[date].available_seats,
                prices=flight.dates[date].prices,
            )
            results.append(direct_flight)
    return results


def _payment_for_update(db: FlightDB, user_id: str, payment_id: str, total_price: int) -> Optional[Payment]:
    user = _get_user(db, user_id)

    if payment_id not in user.payment_methods:
        raise ValueError("Payment method not found")
    payment_method = user.payment_methods[payment_id]

    if payment_method.source == "certificate":
        raise ValueError("Certificate cannot be used to update reservation")
    elif payment_method.source == "gift_card" and payment_method.amount < total_price:
        raise ValueError("Gift card balance is not enough")

    if payment_method.source == "gift_card":
        payment_method.amount -= total_price

    if total_price == 0:
        return None
    return Payment(payment_id=payment_id, amount=total_price)


_ALLOWED_CABINS = {"business", "economy", "basic_economy"}


def _normalize_cabin(cabin: str) -> str:
    if not isinstance(cabin, str) or not cabin.strip():
        raise ValueError("Cabin must be a non-empty string")
    normalized = cabin.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized == "basiceconomy":
        normalized = "basic_economy"
    if normalized not in _ALLOWED_CABINS:
        raise ValueError(
            f"Invalid cabin '{cabin}'. Expected one of: business, economy, basic_economy"
        )
    return normalized


def _resolve_payment_id(payment_id: str = "", payment_method_id: str = "") -> str:
    resolved = payment_id or payment_method_id
    if not resolved:
        raise ValueError("payment_id is required")
    return resolved


def _serialize_reservation_with_aliases(reservation: Reservation) -> str:
    data = reservation.model_dump(mode="json")
    payment_history = data.get("payment_history", [])
    if isinstance(payment_history, list):
        for entry in payment_history:
            if (
                isinstance(entry, dict)
                and "payment_id" in entry
                and "payment_method_id" not in entry
            ):
                entry["payment_method_id"] = entry["payment_id"]
    return json.dumps(data, indent=2)


def _serialize_user_with_aliases(user) -> str:
    data = user.model_dump(mode="json")
    payment_methods = data.get("payment_methods", {})
    if isinstance(payment_methods, dict):
        for _, method in payment_methods.items():
            if isinstance(method, dict) and "source" in method and "type" not in method:
                method["type"] = method["source"]
    return json.dumps(data, indent=2)


def _get_data_model_defs() -> Dict[str, dict]:
    model_classes = [
        AirportCode,
        Certificate,
        DirectFlight,
        FlightDateStatusAvailable,
        FlightInfo,
        Passenger,
        Payment,
        ReservationFlight,
        Reservation,
        User,
    ]
    defs: Dict[str, dict] = {}
    for model_cls in model_classes:
        model_name = getattr(model_cls, "__name__", str(model_cls))
        model_json_schema = getattr(model_cls, "model_json_schema", None)
        if not callable(model_json_schema):
            continue
        schema = model_json_schema(ref_template="#/$defs/{model}")
        defs[model_name] = {
            "description": schema.get("description", ""),
            "properties": schema.get("properties", {}),
        }
    return defs


def _get_tool_metadata_payload() -> Dict[str, Any]:
    ordered_actions = [
        "book_reservation",
        "calculate",
        "cancel_reservation",
        "get_flight_status",
        "get_reservation_details",
        "get_user_details",
        "list_all_airports",
        "search_direct_flight",
        "search_onestop_flight",
        "send_certificate",
        "transfer_to_human_agents",
        "update_reservation_baggages",
        "update_reservation_flights",
        "update_reservation_passengers",
    ]

    return {
        "ordered_actions": ordered_actions,
        "return_types": {
            "book_reservation": "str (JSON)",
            "calculate": "str",
            "cancel_reservation": "str (JSON)",
            "get_flight_status": "str",
            "get_reservation_details": "str (JSON)",
            "get_user_details": "str (JSON)",
            "list_all_airports": "str (JSON)",
            "search_direct_flight": "str (JSON)",
            "search_onestop_flight": "str (JSON)",
            "send_certificate": "str",
            "transfer_to_human_agents": "str",
            "update_reservation_baggages": "str (JSON)",
            "update_reservation_flights": "str (JSON)",
            "update_reservation_passengers": "str (JSON)",
        },
        "semantic_types": {
            "book_reservation": "Reservation",
            "cancel_reservation": "Reservation",
            "get_reservation_details": "Reservation",
            "get_user_details": "User",
            "list_all_airports": "list[AirportCode]",
            "search_direct_flight": "list[DirectFlight]",
            "search_onestop_flight": "list[list[DirectFlight]]",
            "update_reservation_baggages": "Reservation",
            "update_reservation_flights": "Reservation",
            "update_reservation_passengers": "Reservation",
        },
        "data_model_defs": _get_data_model_defs(),
    }


# ==================== READ / GENERIC TOOLS ====================

@mcp.tool()
def calculate(expression: str, session_id: str = "") -> str:
    """
    Calculate the result of a mathematical expression.

    Args:
        expression: The mathematical expression to calculate, such as '2 + 2'. The expression can contain numbers, operators (+, -, *, /), parentheses, and spaces.

    Returns:
        str: The result of the mathematical expression as a string.

    Raises:
        ValueError: If the expression is invalid.
    """
    if not all(char in "0123456789+-*/(). " for char in expression):
        raise ValueError("Invalid characters in expression")
    return str(round(float(eval(expression, {"__builtins__": None}, {})), 2))


@mcp.tool()
def get_reservation_details(reservation_id: str, session_id: str = "") -> str:
    """
    Get the details of a reservation.

    This is the primary lookup method before any reservation write action.
    Use this to verify current status, cabin, flights, passengers, and payment history.

    Args:
        reservation_id: The reservation ID, such as '8JX2WO'.

    Returns:
        str: The reservation details serialized as a JSON string.
    """
    db = get_db(session_id)
    return _serialize_reservation_with_aliases(_get_reservation(db, reservation_id))


@mcp.tool()
def get_user_details(user_id: str, session_id: str = "") -> str:
    """
    Get the details of a user, including their reservations and payment methods.

    Args:
        user_id: The user ID, such as 'sara_doe_496'.

    Returns:
        str: The user details serialized as a JSON string.
    """
    db = get_db(session_id)
    return _serialize_user_with_aliases(_get_user(db, user_id))


@mcp.tool()
def list_all_airports(session_id: str = "") -> str:
    """
    Returns a list of all available airports.

    Returns:
        str: The airport list serialized as a JSON string.
    """
    airports = [
        AirportCode(iata="SFO", city="San Francisco"),
        AirportCode(iata="JFK", city="New York"),
        AirportCode(iata="LAX", city="Los Angeles"),
        AirportCode(iata="ORD", city="Chicago"),
        AirportCode(iata="DFW", city="Dallas"),
        AirportCode(iata="DEN", city="Denver"),
        AirportCode(iata="SEA", city="Seattle"),
        AirportCode(iata="ATL", city="Atlanta"),
        AirportCode(iata="MIA", city="Miami"),
        AirportCode(iata="BOS", city="Boston"),
        AirportCode(iata="PHX", city="Phoenix"),
        AirportCode(iata="IAH", city="Houston"),
        AirportCode(iata="LAS", city="Las Vegas"),
        AirportCode(iata="MCO", city="Orlando"),
        AirportCode(iata="EWR", city="Newark"),
        AirportCode(iata="CLT", city="Charlotte"),
        AirportCode(iata="MSP", city="Minneapolis"),
        AirportCode(iata="DTW", city="Detroit"),
        AirportCode(iata="PHL", city="Philadelphia"),
        AirportCode(iata="LGA", city="LaGuardia"),
    ]
    return _serialize(airports)


@mcp.tool()
def search_direct_flight(origin: str, destination: str, date: str, session_id: str = "") -> str:
    """
    Search for direct flights between two cities on a specific date.

    Args:
        origin: IATA code for origin airport, such as 'JFK'.
        destination: IATA code for destination airport, such as 'LAX'.
        date: Date in YYYY-MM-DD format.

    Returns:
        str: Matching direct flights serialized as a JSON string.
    """
    db = get_db(session_id)
    return _serialize(_search_direct_flight(db, date=date, origin=origin, destination=destination))


@mcp.tool()
def search_onestop_flight(origin: str, destination: str, date: str, session_id: str = "") -> str:
    """
    Search for one-stop flights between two cities on a specific date.

    Args:
        origin: IATA code for origin airport, such as 'JFK'.
        destination: IATA code for destination airport, such as 'LAX'.
        date: Date in YYYY-MM-DD format.

    Returns:
        str: Candidate one-stop itineraries serialized as a JSON string.
    """
    db = get_db(session_id)
    results = []
    for result1 in _search_direct_flight(db, date=date, origin=origin, destination=None):
        result1.date = date
        date2 = (
            f"2024-05-{int(date[-2:]) + 1}"
            if "+1" in result1.scheduled_arrival_time_est
            else date
        )
        for result2 in _search_direct_flight(
            db,
            date=date2,
            origin=result1.destination,
            destination=destination,
            leave_after=result1.scheduled_arrival_time_est,
        ):
            result2.date = date2
            results.append([result1, result2])
    return _serialize(results)


@mcp.tool()
def get_flight_status(flight_number: str, date: str, session_id: str = "") -> str:
    """
    Get the status of a flight.

    Args:
        flight_number: The flight number.
        date: The date of the flight.

    Returns:
        str: The status of the flight.
    """
    db = get_db(session_id)
    return _get_flight_instance(db, flight_number, date).status


@mcp.tool()
def transfer_to_human_agents(summary: str, session_id: str = "") -> str:
    """
    Transfer the user to a human agent with a summary.

    Args:
        summary: Concise factual summary of issue and attempts.

    Returns:
        str: Confirmation string.
    """
    return "Transfer successful"


@mcp.tool()
def get_execution_error_hint(error_msg: str, code: str = "", session_id: str = "") -> str:
    """
    Return a recovery hint for sandbox execution/tool errors.

    Args:
        error_msg: The root error message produced by sandbox/tool execution.
        code: The executed python code snippet (optional, used for pattern detection).

    Returns:
        str: A concise hint string. Empty string if no specific hint applies.
    """
    return analyze_execution_error(error_msg=error_msg, code=code, domain="airline")


@mcp.tool()
def get_tool_metadata(session_id: str = "") -> str:
    """Return metadata used to build execute_python action/data-model description.

    Returns:
        JSON string with keys like return_types and data_model_defs.
    """
    return json.dumps(_get_tool_metadata_payload())


# ==================== WRITE TOOLS ====================

@mcp.tool()
def send_certificate(user_id: str, amount: int, session_id: str = "") -> str:
    """
    Send a certificate to a user.

    Args:
        user_id: User ID such as 'sara_doe_496'.
        amount: Certificate amount.

    Returns:
        str: Confirmation message.
    """
    db = get_db(session_id)
    user = _get_user(db, user_id)
    for payment_id in [f"certificate_{id}" for id in _get_new_payment_id()]:
        if payment_id not in user.payment_methods:
            user.payment_methods[payment_id] = Certificate(
                id=payment_id,
                amount=amount,
                source="certificate",
            )
            db.save()
            return f"Certificate {payment_id} added to user {user_id} with amount {amount}."
    raise ValueError("Too many certificates")


@mcp.tool()
def book_reservation(
    user_id: str,
    origin: str,
    destination: str,
    flight_type: str,
    cabin: str,
    flights: List[dict],
    passengers: List[dict],
    payment_methods: List[dict],
    total_baggages: int,
    nonfree_baggages: int,
    insurance: str,
    session_id: str = "",
) -> str:
    """
    Book a reservation.

    Args:
        user_id: User ID such as 'sara_doe_496'.
        origin: Origin IATA code.
        destination: Destination IATA code.
        flight_type: 'one_way' or 'round_trip'.
        cabin: Cabin class.
        flights: List of {flight_number, date} objects.
        passengers: List of passenger objects.
        payment_methods: List of payment objects.
        total_baggages: Total baggage count.
        nonfree_baggages: Non-free baggage count.
        insurance: 'yes' or 'no'.

    Returns:
        str: Reservation details serialized as a JSON string.
    """
    db = get_db(session_id)
    user = _get_user(db, user_id)
    reservation_id = _get_new_reservation_id(db)
    cabin = _normalize_cabin(cabin)

    if all(isinstance(flight, dict) for flight in flights):
        flights = [FlightInfo(**flight) for flight in flights]
    if all(isinstance(passenger, dict) for passenger in passengers):
        passengers = [Passenger(**passenger) for passenger in passengers]
    if all(isinstance(payment_method, dict) for payment_method in payment_methods):
        normalized_payment_methods = []
        for payment_method in payment_methods:
            method = dict(payment_method)
            if "payment_id" not in method and "payment_method_id" in method:
                method["payment_id"] = method["payment_method_id"]
            normalized_payment_methods.append(method)
        payment_methods = normalized_payment_methods
        payment_methods = [Payment(**payment_method) for payment_method in payment_methods]

    reservation = Reservation(
        reservation_id=reservation_id,
        user_id=user_id,
        origin=origin,
        destination=destination,
        flight_type=flight_type,
        cabin=cabin,
        flights=[],
        passengers=deepcopy(passengers),
        payment_history=deepcopy(payment_methods),
        created_at=_get_datetime(),
        total_baggages=total_baggages,
        nonfree_baggages=nonfree_baggages,
        insurance=insurance,
    )

    total_price = 0
    all_flights_date_data: list[FlightDateStatusAvailable] = []

    for flight_info in flights:
        flight_number = flight_info.flight_number
        flight = _get_flight(db, flight_number)
        flight_date_data = _get_flight_instance(db, flight_number, flight_info.date)

        if not isinstance(flight_date_data, FlightDateStatusAvailable):
            raise ValueError(
                f"Flight {flight_number} not available on date {flight_info.date}"
            )
        if flight_date_data.available_seats[cabin] < len(passengers):
            raise ValueError(f"Not enough seats on flight {flight_number}")

        price = flight_date_data.prices[cabin]
        reservation.flights.append(
            ReservationFlight(
                origin=flight.origin,
                destination=flight.destination,
                flight_number=flight_number,
                date=flight_info.date,
                price=price,
            )
        )
        all_flights_date_data.append(flight_date_data)
        total_price += price * len(passengers)

    if insurance == "yes":
        total_price += 30 * len(passengers)
    total_price += 50 * nonfree_baggages

    for payment_method in payment_methods:
        payment_id = payment_method.payment_id
        amount = payment_method.amount
        if payment_id not in user.payment_methods:
            raise ValueError(f"Payment method {payment_id} not found")
        user_payment_method = user.payment_methods[payment_id]
        if user_payment_method.source in {"gift_card", "certificate"}:
            if user_payment_method.amount < amount:
                raise ValueError(f"Not enough balance in payment method {payment_id}")

    total_payment = sum(payment.amount for payment in payment_methods)
    if total_payment != total_price:
        raise ValueError(
            f"Payment amount does not add up, total price is {total_price}, but paid {total_payment}"
        )

    for payment_method in payment_methods:
        payment_id = payment_method.payment_id
        amount = payment_method.amount
        user_payment_method = user.payment_methods[payment_id]
        if user_payment_method.source == "gift_card":
            user_payment_method.amount -= amount
        elif user_payment_method.source == "certificate":
            user.payment_methods.pop(payment_id)

    for flight_date_data in all_flights_date_data:
        flight_date_data.available_seats[cabin] -= len(passengers)

    db.reservations[reservation_id] = reservation
    db.users[user_id].reservations.append(reservation_id)
    db.save()
    return _serialize_reservation_with_aliases(reservation)


@mcp.tool()
def cancel_reservation(reservation_id: str, session_id: str = "") -> str:
    """
    Cancel the whole reservation.

    Args:
        reservation_id: Reservation ID such as 'ZFA04Y'.

    Returns:
        str: Updated reservation serialized as a JSON string.
    """
    db = get_db(session_id)
    reservation = _get_reservation(db, reservation_id)

    refunds = []
    for payment in reservation.payment_history:
        refunds.append(Payment(payment_id=payment.payment_id, amount=-payment.amount))
    reservation.payment_history.extend(refunds)
    reservation.status = "cancelled"

    db.save()
    return _serialize_reservation_with_aliases(reservation)


@mcp.tool()
def update_reservation_baggages(
    reservation_id: str,
    total_baggages: int,
    nonfree_baggages: int,
    payment_id: str = "",
    payment_method_id: str = "",
    session_id: str = "",
) -> str:
    """
    Update the baggage information of a reservation.

    Args:
        reservation_id: Reservation ID such as 'ZFA04Y'.
        total_baggages: Final total baggage count.
        nonfree_baggages: Final non-free baggage count.
        payment_id: Payment method ID from the booking user.
        payment_method_id: Alias for payment_id (accepted for compatibility).

    Returns:
        str: Updated reservation serialized as a JSON string.
    """
    db = get_db(session_id)
    reservation = _get_reservation(db, reservation_id)
    resolved_payment_id = _resolve_payment_id(payment_id, payment_method_id)

    total_price = 50 * max(0, nonfree_baggages - reservation.nonfree_baggages)
    payment = _payment_for_update(db, reservation.user_id, resolved_payment_id, total_price)
    if payment is not None:
        reservation.payment_history.append(payment)

    reservation.total_baggages = total_baggages
    reservation.nonfree_baggages = nonfree_baggages
    db.save()
    return _serialize_reservation_with_aliases(reservation)


@mcp.tool()
def update_reservation_flights(
    reservation_id: str,
    cabin: str,
    flights: List[dict],
    payment_id: str = "",
    payment_method_id: str = "",
    session_id: str = "",
) -> str:
    """
    Update the flight information of a reservation.

    IMPORTANT:
    - Provide COMPLETE updated itinerary, not just changed legs.
    - Use exact flight numbers/dates from search results.

    Args:
        reservation_id: Reservation ID such as 'ZFA04Y'.
        cabin: Updated cabin class. Accepts business/economy/basic_economy (also tolerant to spaces/hyphens).
        flights: Complete itinerary as list of {flight_number, date}.
        payment_id: Payment method ID from booking user.
        payment_method_id: Alias for payment_id (accepted for compatibility).

    Returns:
        str: Updated reservation serialized as a JSON string.
    """
    db = get_db(session_id)
    reservation = _get_reservation(db, reservation_id)
    user = _get_user(db, reservation.user_id)
    cabin = _normalize_cabin(cabin)
    resolved_payment_id = _resolve_payment_id(payment_id, payment_method_id)

    if all(isinstance(flight, dict) for flight in flights):
        flights = [FlightInfo(**flight) for flight in flights]

    total_price = 0
    reservation_flights = []
    for flight_info in flights:
        matching_reservation_flight = next(
            (
                reservation_flight
                for reservation_flight in reservation.flights
                if reservation_flight.flight_number == flight_info.flight_number
                and reservation_flight.date == flight_info.date
                and cabin == reservation.cabin
            ),
            None,
        )
        if matching_reservation_flight:
            total_price += matching_reservation_flight.price * len(reservation.passengers)
            reservation_flights.append(matching_reservation_flight)
            continue

        flight = _get_flight(db, flight_info.flight_number)
        flight_date_data = _get_flight_instance(db, flight_info.flight_number, flight_info.date)
        if not isinstance(flight_date_data, FlightDateStatusAvailable):
            raise ValueError(
                f"Flight {flight_info.flight_number} not available on date {flight_info.date}"
            )
        if flight_date_data.available_seats[cabin] < len(reservation.passengers):
            raise ValueError(f"Not enough seats on flight {flight_info.flight_number}")

        reservation_flight = ReservationFlight(
            flight_number=flight_info.flight_number,
            date=flight_info.date,
            price=flight_date_data.prices[cabin],
            origin=flight.origin,
            destination=flight.destination,
        )
        total_price += reservation_flight.price * len(reservation.passengers)
        reservation_flights.append(reservation_flight)

    total_price -= sum(flight.price for flight in reservation.flights) * len(reservation.passengers)

    payment = _payment_for_update(db, user.user_id, resolved_payment_id, total_price)
    if payment is not None:
        reservation.payment_history.append(payment)

    reservation.flights = reservation_flights
    reservation.cabin = cabin

    db.save()
    return _serialize_reservation_with_aliases(reservation)


@mcp.tool()
def update_reservation_passengers(
    reservation_id: str,
    passengers: List[dict],
    session_id: str = "",
) -> str:
    """
    Update the passenger information of a reservation.

    Passenger count must exactly match existing reservation passenger count.

    Args:
        reservation_id: Reservation ID such as 'ZFA04Y'.
        passengers: Full list of passenger objects.

    Returns:
        str: Updated reservation serialized as a JSON string.
    """
    db = get_db(session_id)
    reservation = _get_reservation(db, reservation_id)

    if all(isinstance(passenger, dict) for passenger in passengers):
        passengers = [Passenger(**passenger) for passenger in passengers]
    if len(passengers) != len(reservation.passengers):
        raise ValueError("Number of passengers does not match")

    reservation.passengers = deepcopy(passengers)
    db.save()
    return _serialize_reservation_with_aliases(reservation)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Airline MCP Server")
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help="Path to the airline database JSON file",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5052,
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

    os.environ["AIRLINE_DB_PATH"] = args.db_path

    ensure_db(args.db_path)
    get_db()
    print("   Original DB file is READ-ONLY (per-session copies used for mutations)")
    print(f"   Session DB dir: {SESSION_DB_DIR}")

    print("\n🚀 Starting Airline MCP Server...")
    print(f"   Transport: {args.transport}")
    if args.transport == "sse":
        print(f"   Host: {args.host}")
        print(f"   Port: {args.port}")
        print(f"   SSE endpoint: http://{args.host}:{args.port}/sse")

    mcp.run(transport=args.transport, host=args.host, port=args.port)
