import re


def analyze_execution_error(error_msg: str, code: str = "", domain: str = "generic") -> str:
    """Analyze execution/tool errors and return a recovery hint string.

    Domain-specific servers can call this with a domain label to customize messaging.
    """
    if not error_msg:
        return ""

    if "is not defined" in error_msg and "name '" in error_msg:
        match = re.search(r"name '(\w+)' is not defined", error_msg)
        var_name = match.group(1) if match else "variable"

        if domain == "airline":
            common_params = [
                "first_name",
                "last_name",
                "email",
                "user_id",
                "flight_number",
                "reservation_id",
                "origin",
                "destination",
            ]
            if var_name in common_params:
                return (
                    f"ERROR: '{var_name}' is not defined. You must use a STRING LITERAL with "
                    "the actual value from the conversation, not an undefined variable. "
                    "For example, use \"John\" instead of first_name."
                )

        return (
            f"REMINDER: The sandbox is STATELESS. '{var_name}' was not defined in this "
            f"script. Variables from previous execute_python calls do NOT persist. "
            f"You must define all variables in the SAME script. "
            f"If '{var_name}' should be a value from the conversation, use a string literal."
        )

    if "'str' object has no attribute" in error_msg:
        attr_match = re.search(r"'str' object has no attribute '(\w+)'", error_msg)
        attr_name = attr_match.group(1) if attr_match else ""
        return (
            f"You are accessing '.{attr_name}' on a STRING. "
            "actions.* methods return dicts — use bracket notation, not dot access:\n"
            f"  print(result['{attr_name}'])  # Access as dict key, not attribute\n"
            "Also check: iterating over a dict yields keys (strings), not objects. "
            "Use `.items()` to get (key, value) pairs."
        )

    if "string indices must be integers" in error_msg:
        if domain == "airline" and "db." in code:
            return (
                "You are trying to access a string as a dictionary. Common causes: "
                "1) JSON string vs dict confusion, "
                "2) Iterating `db.users` / `db.flights` / `db.reservations` directly (yielding keys)."
            )

        hint_parts = []

        has_json_loads = "json.loads" in code
        has_for_loop = re.search(r"for\s+(\w+)\s+in\s+(\w+)", code)

        if has_json_loads and has_for_loop:
            loop_var = has_for_loop.group(1)
            iterable_var = has_for_loop.group(2)
            key_access = re.search(rf"{re.escape(loop_var)}\[(['\"])\w+\1\]", code)
            if key_access:
                hint_parts.append(
                    f"You parsed the JSON correctly, but the result is a DICT (not a list of objects).\n"
                    f"When you write `for {loop_var} in {iterable_var}:`, Python iterates over the dict KEYS (strings).\n"
                    f"Then `{loop_var}['...']` fails because {loop_var} is a string like 'T-Shirt', not a dict.\n\n"
                    f"FIX: Use `.items()` to get key-value pairs:\n"
                    f"  for key, value in {iterable_var}.items():\n"
                    f"      print(key, value)\n\n"
                    f"Check the API REFERENCE for the exact return shape of each action."
                )

        if hint_parts:
            return "\n".join(hint_parts)

        return (
            "You are trying to use string indexing (e.g., x['key']) on a STRING value. Common causes:\n"
            "1) The data is a DICT, not a list of objects. "
            "Iterating over a dict yields keys (strings), not objects. "
            "Use `.items()` to get (key, value) pairs, or `.values()` for values only.\n"
            "2) A field contains ID strings, not objects. "
            "Fetch the full object using the appropriate actions.* method.\n"
            "Check the API REFERENCE Usage examples for the correct iteration pattern."
        )

    if "'dict' object has no attribute 'value'" in error_msg:
        return "Dictionaries have a `.values()` method (plural), not `.value`. Did you mean `.values()`?"

    if domain == "airline" and "name 'db' is not defined" in error_msg:
        return "The `db` variable is available in the global scope. You do not need to import it."

    if "missing 1 required positional argument: 'code'" in error_msg:
        return 'The tool call is missing the \'code\' argument. Ensure your JSON tool call has {"code": "..."}.'

    if "'builtin_function_or_method' object is not iterable" in error_msg:
        return (
            "You are trying to iterate over a method instead of calling it. "
            "Check if you forgot parentheses: `.items()` not `.items`, "
            "`.values()` not `.values`."
        )

    if "input() is not available" in error_msg:
        return (
            "You cannot use input() in the sandbox. "
            "Extract the information from the conversation history instead. "
            "If you don't have the information yet, send a message asking the user for it."
        )

    if "Import of" in error_msg and "not allowed" in error_msg:
        return "External imports are not allowed in the sandbox. Use the provided 'actions' object and built-in modules (json, math, re)."

    if "__name__" in error_msg or 'is an invalid attribute name because it starts with "_"' in error_msg:
        return "Dunder attributes (like __name__) are blocked by sandbox security."

    if "not found" in error_msg.lower() and "Error calling tool" in error_msg:
        if domain == "airline":
            if "User" in error_msg and "not found" in error_msg:
                return "The user was not found. Make sure you are using the ACTUAL ID provided by the user."
            if "Reservation" in error_msg and "not found" in error_msg:
                return "The reservation was not found. Make sure you are using the ACTUAL reservation ID provided by the user."
            if "Flight" in error_msg and "not found" in error_msg:
                return "The flight was not found. Check the flight number and date."
        return (
            "A value was not found. Make sure you are using ACTUAL values retrieved from "
            "previous tool calls or provided by the user, NOT placeholder or example values. "
            "If you need an ID, look it up first using the appropriate query/lookup action."
        )

    if domain == "airline" and "'FlightDB' object has no attribute" in error_msg:
        return (
            "The `db` object is a container. It has NO search methods. "
            "You must iterate over `db.users.values()`, `db.flights.values()`, "
            "`db.reservations.values()` to find items."
        )

    if domain == "airline" and "'str' object has no attribute" in error_msg and "db." in code:
        return (
            "You might be iterating over a dictionary (for example, `for u in db.users:`). "
            "This yields keys (strings). Use `.values()` to iterate over objects "
            "(for example, `for u in db.users.values():`)."
        )

    if domain == "airline" and "'AirlineTools' object has no attribute" in error_msg:
        return (
            "You are trying to call a method that does not exist on the `actions` object. "
            "Please check the list of AVAILABLE ACTIONS in the system prompt."
        )

    if "object has no attribute" in error_msg and "actions" in code.lower():
        return (
            "You called a method that does not exist. "
            "Check the API REFERENCE in the system prompt for available actions."
        )

    if domain == "retail" and "#" in code and "Order not found" in error_msg:
        return "Use the exact order ID returned by tools (including '#'). If user omitted '#', normalize before lookup."

    return ""