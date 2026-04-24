#!/usr/bin/env python3
"""
MCP Sandbox Server - Multi-Engine Implementation

Supports both code-mode (utcp_code_mode) and Monty (pydantic-monty)
for secure Python code execution.
Connects to an MCP tools server and exposes execute_python via MCP.

Features (matching code_tools.py behaviour):
- Dynamic tool description auto-generated from the tools server's list_tools
- Comprehensive _analyze_error_message hints
- Session-aware tool calls (mcp-session-id header)
- Self-sufficient: parses descriptions, params, return types from standard MCP tool listings

Usage:
    python mcp_server_codemode.py --port 5051 --tools-url http://localhost:5050/sse --engine codemode
    python mcp_server_codemode.py --port 5051 --tools-url http://localhost:5050/sse --engine monty
"""

import argparse
import asyncio
import json
import logging
import re
import threading
import time
import warnings

# Suppress RestrictedPython's benign warning about the 'printed' variable.
# We read print output via __shared_print_collector__, not the 'printed' local.
warnings.filterwarnings(
    "ignore",
    message=r".*Prints, but never reads 'printed' variable.*",
    category=SyntaxWarning,
    module=r"RestrictedPython\.compile",
)
from dataclasses import dataclass, field
from typing import Annotated, Any, Callable, Dict, List, Mapping, Optional, Tuple
from uuid import uuid4

from fastmcp import FastMCP, Context
from mcp import ClientSession
from mcp.client.sse import sse_client

try:
    from utcp_code_mode import CodeModeUtcpClient
    _CODEMODE_IMPORT_ERROR: Optional[Exception] = None
except Exception as _codemode_exc:
    CodeModeUtcpClient = object  # type: ignore[assignment]
    _CODEMODE_IMPORT_ERROR = _codemode_exc

try:
    from utcp.data.tool import Tool, JsonSchema
    from utcp.data.call_template import CallTemplate
    _UTCP_IMPORT_ERROR: Optional[Exception] = None
except Exception as _utcp_exc:
    class Tool:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            pass

    class JsonSchema:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            pass

    class CallTemplate:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            pass

    _UTCP_IMPORT_ERROR = _utcp_exc

try:
    import pydantic_monty
    _MONTY_IMPORT_ERROR: Optional[Exception] = None
except Exception as _monty_exc:
    pydantic_monty = None  # type: ignore[assignment]
    _MONTY_IMPORT_ERROR = _monty_exc

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [SANDBOX] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ==================== ERROR ANALYSIS (delegated to tools server) ====================


async def _fetch_remote_error_hint(
    tools_url: str,
    session_id: str,
    error_msg: str,
    code: str,
) -> str:
    """Fetch error hint from tools server if it exposes get_execution_error_hint."""
    headers = {}
    if session_id:
        headers["mcp-session-id"] = session_id

    async with sse_client(tools_url, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "get_execution_error_hint",
                {
                    "error_msg": error_msg,
                    "code": code,
                    "session_id": session_id,
                },
            )
            if getattr(result, "isError", False):
                return ""

            if hasattr(result, "content") and result.content:
                parts = [item.text for item in result.content if hasattr(item, "text")]
                return "\n".join(parts).strip()
            return ""


async def _fetch_remote_tool_metadata(tools_url: str, session_id: str = "") -> Dict[str, Any]:
    """Fetch metadata payload from tools server MCP get_tool_metadata tool."""
    headers = {}
    if session_id:
        headers["mcp-session-id"] = session_id

    try:
        async with sse_client(tools_url, headers=headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "get_tool_metadata",
                    {"session_id": session_id},
                )
                if getattr(result, "isError", False):
                    return {}

                if hasattr(result, "content") and result.content:
                    parts = [item.text for item in result.content if hasattr(item, "text")]
                    raw = "\n".join(parts).strip()
                    if raw:
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict):
                            return parsed
    except Exception as e:
        logger.warning(f"Could not fetch tool metadata from {tools_url}: {e}")

    return {}


def _analyze_error_message_with_tools(error_msg: str, code: str = "", session_id: str = "") -> str:
    """Resolve error hint from tools server only (no local fallback)."""
    if not error_msg:
        return ""

    effective_session_id = session_id or _session_id

    if _tools_url:
        try:
            asyncio.get_running_loop()
            loop_running = True
        except RuntimeError:
            loop_running = False

        if not loop_running:
            try:
                remote_hint = asyncio.run(
                    _fetch_remote_error_hint(
                        tools_url=_tools_url,
                        session_id=effective_session_id,
                        error_msg=error_msg,
                        code=code,
                    )
                )
                if remote_hint:
                    return remote_hint
            except Exception:
                pass
        else:
            # If already inside an event loop, run in a short-lived thread.
            result_holder = {"hint": ""}

            def _runner():
                try:
                    result_holder["hint"] = asyncio.run(
                        _fetch_remote_error_hint(
                            tools_url=_tools_url,
                            session_id=effective_session_id,
                            error_msg=error_msg,
                            code=code,
                        )
                    )
                except Exception:
                    result_holder["hint"] = ""

            thread = threading.Thread(target=_runner, daemon=True)
            thread.start()
            thread.join(timeout=5)
            if result_holder["hint"]:
                return result_holder["hint"]

    return ""


# ==================== MCP TOOLS CLIENT ====================

@dataclass
class SandboxResult:
    """Result from sandbox code execution."""
    success: bool
    result: Any = None
    output: str = ""
    logs: List[str] = field(default_factory=list)
    error: Optional[str] = None


def _unwrap_exception(exc: BaseException) -> str:
    """Unwrap ExceptionGroup/TaskGroup to extract the root cause message."""
    # Handle ExceptionGroup (Python 3.11+) / TaskGroup errors
    if hasattr(exc, 'exceptions'):
        # ExceptionGroup: recurse into sub-exceptions
        messages = []
        for sub_exc in exc.exceptions:
            messages.append(_unwrap_exception(sub_exc))
        return "; ".join(messages)
    # Handle chained exceptions
    if exc.__cause__:
        return _unwrap_exception(exc.__cause__)
    return str(exc)


class McpToolsClient(CodeModeUtcpClient):
    """CodeModeUtcpClient that proxies tool calls to an MCP server.

    This allows using the code-mode library's secure Python execution
    while calling tools on a remote MCP server.

    Session-aware: passes mcp-session-id header on every SSE connection
    so the tools server can isolate DB state per task.
    """

    def __init__(self, tools_url: str, tools: List[Tool] = None, session_id: str = ""):
        """Initialize with MCP server URL and discovered tools.

        Args:
            tools_url: SSE URL of the MCP tools server
            tools: Pre-discovered list of Tool objects
            session_id: Session ID to pass as mcp-session-id header
        """
        self._tools_url = tools_url
        self._tool_objects = tools or []
        self._tool_function_cache: Dict[str, str] = {}
        self._session_id = session_id

        logger.info(f"McpToolsClient initialized with {len(self._tool_objects)} tools, session={session_id[:8] if session_id else 'none'}...")

    async def call_tool(self, tool_name: str, tool_args: Dict[str, Any] = None) -> Any:
        """Call a tool on the MCP server."""
        if tool_args is None:
            tool_args = {}

        # Strip "actions." prefix if present (code-mode adds this)
        mcp_tool_name = tool_name
        if tool_name.startswith("actions."):
            mcp_tool_name = tool_name[8:]  # Remove "actions." prefix

        logger.info(f"Calling MCP tool: {mcp_tool_name} (from {tool_name})")

        # Inject session_id for per-session DB isolation on the tools server
        if self._session_id:
            tool_args["session_id"] = self._session_id

        try:
            headers = {}
            if self._session_id:
                headers["mcp-session-id"] = self._session_id

            async with sse_client(self._tools_url, headers=headers) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    # Call the tool
                    result = await session.call_tool(mcp_tool_name, tool_args)

                    # Extract text content from result
                    text_content = ""
                    if hasattr(result, 'content') and result.content:
                        contents = []
                        for item in result.content:
                            if hasattr(item, 'text'):
                                contents.append(item.text)
                        text_content = "\n".join(contents) if contents else str(result)
                    else:
                        text_content = str(result)

                    # Check if the MCP tool reported an error
                    if getattr(result, 'isError', False):
                        raise RuntimeError(text_content or "Tool returned an error")

                    return text_content

        except RuntimeError:
            # Re-raise RuntimeError (from isError check above or tool_function wrapper)
            raise
        except BaseException as e:
            # Unwrap ExceptionGroup / TaskGroup to get the real error message
            root_cause = _unwrap_exception(e)
            logger.warning(f"MCP tool call failed: {mcp_tool_name}: {root_cause}")
            raise RuntimeError(f"{root_cause}")

    async def get_tools(self) -> List[Tool]:
        """Get all registered tools."""
        return self._tool_objects

    def call_tool_sync(self, tool_name: str, tool_args: Dict[str, Any] = None) -> Any:
        """Call a tool synchronously, safe even if an event loop is already running."""
        if tool_args is None:
            tool_args = {}

        try:
            asyncio.get_running_loop()
            loop_running = True
        except RuntimeError:
            loop_running = False

        if not loop_running:
            return asyncio.run(self.call_tool(tool_name, tool_args))

        result_holder: Dict[str, Any] = {"result": None, "error": None}

        def _runner() -> None:
            try:
                result_holder["result"] = asyncio.run(self.call_tool(tool_name, tool_args))
            except BaseException as exc:
                result_holder["error"] = exc

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join(timeout=30)

        if thread.is_alive():
            raise RuntimeError(f"Timed out calling MCP tool '{tool_name}'")

        if result_holder["error"] is not None:
            error = result_holder["error"]
            if isinstance(error, RuntimeError):
                raise error
            raise RuntimeError(_unwrap_exception(error))

        return result_holder["result"]

    async def register_manual(self, *args, **kwargs):
        pass

    async def register_manuals(self, *args, **kwargs):
        pass

    async def deregister_manual(self, *args, **kwargs):
        pass

    async def search_tools(self, query: str, limit: int = 10, **kwargs):
        """Simple search through tools."""
        query_lower = query.lower()
        results = []
        for tool in self._tool_objects:
            if query_lower in tool.name.lower() or query_lower in tool.description.lower():
                results.append(tool)
                if len(results) >= limit:
                    break
        return results

    async def _create_execution_context(self, tools: List[Tool], logs: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create execution context with RestrictedPython guards.

        Override parent to:
        1. Add missing _getiter_, _getitem_ guards for RestrictedPython
        2. Create tool functions that handle positional arguments
        """
        from RestrictedPython import safe_globals
        from RestrictedPython.Eval import default_guarded_getiter, default_guarded_getitem
        from RestrictedPython.Guards import guarded_iter_unpack_sequence, full_write_guard
        from RestrictedPython.PrintCollector import PrintCollector
        import concurrent.futures

        # Start with RestrictedPython's safe globals
        context: Dict[str, Any] = safe_globals.copy()

        # Add RestrictedPython guards for iteration, item access, and writes
        context['_getiter_'] = default_guarded_getiter
        context['_getitem_'] = default_guarded_getitem
        context['_iter_unpack_sequence_'] = guarded_iter_unpack_sequence
        context['_getattr_'] = getattr
        context['_write_'] = full_write_guard  # Needed for list.append(), +=, etc.

        # _inplacevar_ is needed for augmented assignments (+=, -=, *=, etc.)
        # RestrictedPython passes the OPERATOR STRING (e.g. '+='), not a callable.
        def _inplacevar_(op, x, y):
            if op == '+=':
                return x + y
            elif op == '-=':
                return x - y
            elif op == '*=':
                return x * y
            elif op == '/=':
                return x / y
            elif op == '//=':
                return x // y
            elif op == '%=':
                return x % y
            elif op == '**=':
                return x ** y
            elif op == '<<=':
                return x << y
            elif op == '>>=':
                return x >> y
            elif op == '&=':
                return x & y
            elif op == '^=':
                return x ^ y
            elif op == '|=':
                return x | y
            # Fallback: try calling op in case a future RestrictedPython passes a callable
            elif callable(op):
                return op(x, y)
            else:
                raise ValueError(f'Unknown in-place operator: {op}')
        context['_inplacevar_'] = _inplacevar_

        # Create restricted import
        SAFE_MODULES = {'json', 'math', 'datetime', 'time', 're', 'typing', 'collections', 'itertools'}

        def restricted_import(name, *args, **kwargs):
            if name in SAFE_MODULES:
                return __import__(name, *args, **kwargs)
            raise ImportError(f"Import of '{name}' is not allowed")

        # Add builtins
        if '__builtins__' in context and isinstance(context['__builtins__'], dict):
            context['__builtins__'].update({
                '__import__': restricted_import,
                'list': list, 'dict': dict, 'set': set, 'tuple': tuple,
                'str': str, 'int': int, 'float': float, 'bool': bool,
                'len': len, 'range': range, 'isinstance': isinstance,
                'hasattr': hasattr, 'getattr': getattr, 'type': type,
                'max': max, 'min': min, 'sum': sum, 'abs': abs, 'round': round,
                'sorted': sorted, 'reversed': reversed, 'enumerate': enumerate,
                'zip': zip, 'filter': filter, 'map': map, 'next': next,
            })

        # Add safe modules
        context.update({
            'json': __import__('json'),
            'math': __import__('math'),
            'datetime': __import__('datetime'),
            'time': __import__('time'),
            're': __import__('re'),
            '__import__': restricted_import,
        })

        # Set up print collector
        shared_print_collector = PrintCollector()

        def print_factory(_getattr=None):
            return shared_print_collector

        context['_print_'] = print_factory
        context['_print'] = shared_print_collector
        context['__shared_print_collector__'] = shared_print_collector

        # Create tool functions that handle BOTH positional and keyword arguments
        def make_tool_function(tool_obj: Tool):
            """Create a tool function that handles positional args."""
            tool_name_ref = tool_obj.name

            # Get parameter names from the tool schema
            param_names = []
            if hasattr(tool_obj, 'inputs') and tool_obj.inputs:
                props = getattr(tool_obj.inputs, 'properties', {}) or {}
                param_names = list(props.keys())

            def tool_function(*args, **kwargs):
                # Convert positional args to kwargs using param names
                call_kwargs = dict(kwargs)
                for i, arg in enumerate(args):
                    if i < len(param_names):
                        call_kwargs[param_names[i]] = arg
                    else:
                        # Fallback for extra positional args
                        call_kwargs[f'arg{i}'] = arg

                try:
                    logger.info(f"Tool call: {tool_name_ref} with args: {list(call_kwargs.keys())}")

                    # Run the async tool call in a thread to avoid event loop issues
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, self.call_tool(tool_name_ref, call_kwargs))
                        result = future.result()

                    logger.info(f"Tool call {tool_name_ref} completed")

                    # Auto-parse JSON strings into dicts/lists so user code
                    # can do direct field access (e.g. order['status'])
                    # without needing json.loads()
                    if isinstance(result, str) and result and result[0] in '{[':
                        try:
                            result = json.loads(result)
                        except (json.JSONDecodeError, ValueError):
                            pass  # Return raw string if not valid JSON

                    return result
                except RuntimeError:
                    # Already a clean error from call_tool — pass through as-is
                    raise
                except BaseException as error:
                    root_cause = _unwrap_exception(error)
                    logger.warning(f"Tool call {tool_name_ref} failed: {root_cause}")
                    raise RuntimeError(f"Error calling tool '{tool_name_ref}': {root_cause}")

            return tool_function

        # Add tool functions organized by manual name
        for tool in tools:
            if '.' in tool.name:
                manual_name, *tool_parts = tool.name.split('.')
                tool_name = '_'.join(tool_parts)

                # Create manual namespace object if it doesn't exist
                if manual_name not in context:
                    context[manual_name] = type('Manual', (), {})()

                # Add the tool function to the manual namespace
                setattr(context[manual_name], tool_name, make_tool_function(tool))
            else:
                context[tool.name] = make_tool_function(tool)

        return context


# ==================== TOOL DISCOVERY ====================

async def discover_mcp_tools(tools_url: str) -> List[Tool]:
    """Discover tools from an MCP server and convert to UTCP Tool objects."""
    if _UTCP_IMPORT_ERROR is not None:
        logger.warning("UTCP packages unavailable; skipping codemode tool discovery: %s", _UTCP_IMPORT_ERROR)
        return []

    tools = []
    internal_tools = {
        "get_data_model_schema",
        "get_tool_metadata",
        "reset_db_session",
        "list_active_sessions",
        "get_execution_error_hint",
    }

    try:
        async with sse_client(tools_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.list_tools()

                for mcp_tool in result.tools:
                    if mcp_tool.name in internal_tools:
                        continue
                    # Add "actions." prefix for code-mode namespace
                    tool_name = f"actions.{mcp_tool.name}"

                    # Parse input schema
                    input_schema = mcp_tool.inputSchema if hasattr(mcp_tool, 'inputSchema') else {}
                    properties = {}
                    if isinstance(input_schema, dict) and 'properties' in input_schema:
                        properties = {k: v for k, v in input_schema['properties'].items()
                                      if k != 'session_id'}  # Hide internal param

                    tool = Tool(
                        name=tool_name,
                        description=mcp_tool.description or f"MCP tool: {mcp_tool.name}",
                        inputs=JsonSchema(type="object", properties=properties),
                        outputs=JsonSchema(type="object"),
                        tags=["mcp"],
                        tool_call_template=CallTemplate(name="mcp", call_template_type="mcp"),
                    )
                    tools.append(tool)

        logger.info(f"Discovered {len(tools)} MCP tools")
        return tools

    except Exception as e:
        logger.warning(f"Could not discover tools from {tools_url}: {e}")
        return []


async def discover_tools(tools_url: str) -> Dict[str, dict]:
    """Discover available tools from the MCP tools server (flat dict for description generation)."""
    try:
        async with sse_client(tools_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.list_tools()
                tools = {}
                for tool in result.tools:
                    params = tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                    # Filter out internal session_id parameter
                    if isinstance(params, dict) and 'properties' in params:
                        filtered_props = {k: v for k, v in params['properties'].items()
                                          if k != 'session_id'}
                        params = dict(params)
                        params['properties'] = filtered_props
                    tools[tool.name] = {
                        "description": tool.description or "",
                        "parameters": params,
                    }
                return tools
    except Exception as e:
        logger.warning(f"Could not discover tools from {tools_url}: {e}")
        return {}


def _parse_metadata_from_tools(tools_map: Dict[str, dict]) -> dict:
    """Extract metadata (short descriptions, param descriptions, return types)
    directly from the MCP tool listings without requiring a special metadata tool.

    Parses the tool description (docstring) and inputSchema properties.

    Returns dict with keys:
    - return_types: {tool_name: return_type_str}
    - short_descriptions: {tool_name: first_sentence}
    - param_descriptions: {tool_name: {param_name: description}}
    """
    return_types: Dict[str, str] = {}
    short_descriptions: Dict[str, str] = {}
    param_descriptions: Dict[str, Dict[str, str]] = {}

    for name, info in tools_map.items():
        desc = info.get("description", "")

        # --- Short description: full first line (used in signature) ---
        first_line = desc.split('\n')[0].strip() if desc else ""
        short_desc = first_line.rstrip('.') if first_line else name
        short_descriptions[name] = short_desc

        # --- Return type: all MCP tools return JSON strings, but parse Returns: section ---
        ret_type = "str"
        if '\nReturns:' in desc or '\n    Returns:' in desc:
            # Try to detect if it mentions JSON / dict-like returns
            returns_section = desc.split('Returns:')[-1].strip().split('\n')[0].strip()
            if 'json' in returns_section.lower() or 'dict' in returns_section.lower():
                ret_type = "str (JSON)"
            elif returns_section:
                ret_type = "str"
        return_types[name] = ret_type

        # --- Param descriptions: from inputSchema properties ---
        schema = info.get("parameters", {})
        properties = schema.get("properties", {})
        tool_params = {}
        for param_name, param_info in properties.items():
            p_desc = param_info.get("description", "")
            if p_desc:
                tool_params[param_name] = p_desc.strip().rstrip('.')
        if tool_params:
            param_descriptions[name] = tool_params

    return {
        "return_types": return_types,
        "short_descriptions": short_descriptions,
        "param_descriptions": param_descriptions,
    }


# ==================== DYNAMIC DESCRIPTION GENERATION ====================

def _generate_dynamic_description(
    tools_map: Dict[str, dict],
    tool_metadata: Dict[str, Any] = None,
) -> str:
    """Auto-generate a description of all available actions.

    Produces output matching code_tools.py's _generate_actions_description():
    - Signature line: `- actions.name(params) -> ReturnType: First sentence of description`
    - Parameter descriptions indented below
    - DATA MODEL REFERENCE section with compact type definitions

    Works self-sufficiently from MCP list_tools data. If tool_metadata is provided
    (e.g. from a get_tool_metadata tool), it will be used as an override.
    """
    # Parse metadata directly from tools_map (always available)
    parsed = _parse_metadata_from_tools(tools_map)

    # Allow external tool_metadata to override parsed values
    if tool_metadata:
        for key in ("return_types", "short_descriptions", "param_descriptions"):
            if key in tool_metadata and tool_metadata[key]:
                parsed[key].update(tool_metadata[key])

    return_types = parsed["return_types"]
    short_descriptions = parsed["short_descriptions"]
    param_descriptions = parsed["param_descriptions"]
    long_descriptions = (tool_metadata or {}).get("long_descriptions", {})
    param_display_names = (tool_metadata or {}).get("param_display_names", {})

    # Filter out internal/meta tools that shouldn't be exposed to the agent
    internal_tools = {
        "get_data_model_schema",
        "get_tool_metadata",
        "reset_db_session",
        "list_active_sessions",
        "get_execution_error_hint",
    }

    lines = [
        "API REFERENCE - DO NOT CALL THESE DIRECTLY AS TOOLS.",
        "YOU MUST USE `execute_python` TO CALL THESE FUNCTIONS (e.g. `actions.find_user...`).",
        "",
        "AVAILABLE ACTIONS (call these via actions.method_name(...) in your Python code):",
        ""
    ]

    ordered_actions = (tool_metadata or {}).get("ordered_actions", [])
    iteration_names: List[str]
    if isinstance(ordered_actions, list) and ordered_actions:
        seen = set()
        iteration_names = []
        for action_name in ordered_actions:
            if action_name in tools_map and action_name not in seen:
                iteration_names.append(action_name)
                seen.add(action_name)
        for action_name in tools_map.keys():
            if action_name not in seen:
                iteration_names.append(action_name)
    else:
        iteration_names = list(tools_map.keys())

    for name in iteration_names:
        info = tools_map.get(name, {})
        if name in internal_tools:
            continue

        # Get parameters from schema, applying display name overrides
        params = []
        schema = info.get("parameters", {})
        properties = schema.get("properties", {})
        tool_name_overrides = param_display_names.get(name, {})
        for param_name in properties:
            if param_name == "session_id":
                continue  # Hide internal session parameter from LLM
            display_name = tool_name_overrides.get(param_name, param_name)
            params.append(display_name)
        params_str = ', '.join(params)

        # Get return type (used directly as display type)
        ret_type = return_types.get(name, "string")

        # Get short description (for the signature line)
        short_desc = short_descriptions.get(name, "")

        # Format: - actions.name(params) -> Type: First sentence
        lines.append(f"- actions.{name}({params_str}) -> {ret_type}: {short_desc}")

        # Append parameter descriptions if available
        for param_name, p_desc in param_descriptions.get(name, {}).items():
            lines.append(f"    {param_name}: {p_desc}")

        # Append long description if available (guidance notes like
        # "Ask the customer for confirmation before cancelling.")
        long_desc = long_descriptions.get(name, "")
        if long_desc:
            desc_lines = long_desc.strip().splitlines()
            non_empty = [l for l in desc_lines if l.strip()]
            if non_empty:
                min_indent = min(len(l) - len(l.lstrip()) for l in non_empty)
                for dline in desc_lines:
                    if dline.strip():
                        lines.append(f"    {dline[min_indent:]}")

    # Add DATA MODEL REFERENCE section
    # If tool_metadata provides data_model_defs, use them
    data_model_defs = (tool_metadata or {}).get("data_model_defs", {})
    if data_model_defs:
        lines.append("")
        lines.append("DATA MODEL REFERENCE:")

        for type_name, type_schema in data_model_defs.items():
            properties = type_schema.get('properties', {})

            props = []
            for prop_name, prop_info in properties.items():
                prop_type = prop_info.get('type', '')
                if '$ref' in prop_info:
                    prop_type = prop_info['$ref'].split('/')[-1]
                elif 'anyOf' in prop_info:
                    types = [t.get('$ref', '').split('/')[-1] or t.get('type', '')
                            for t in prop_info['anyOf'] if t.get('type') != 'null']
                    prop_type = ' | '.join(filter(None, types))
                elif prop_info.get('type') == 'array':
                    items = prop_info.get('items', {})
                    item_type = items.get('$ref', '').split('/')[-1] or items.get('type', 'Any')
                    prop_type = f"list[{item_type}]"
                elif prop_info.get('type') == 'object':
                    prop_type = "dict"
                props.append(f"{prop_name}: {prop_type}")

            props_str = ', '.join(props)
            lines.append(f"- {type_name}: {props_str}")

    return '\n'.join(lines)


def get_tools_documentation(available_tools: Dict[str, dict]) -> str:
    """Generate documentation string for available tools."""
    if not available_tools:
        return "No tools discovered. Make sure tools server is running."

    internal_tools = {
        "get_data_model_schema",
        "get_tool_metadata",
        "reset_db_session",
        "list_active_sessions",
        "get_execution_error_hint",
    }

    lines = ["Available actions:"]
    for name, info in sorted(available_tools.items()):
        if name in internal_tools:
            continue
        desc = info.get("description", "")
        if len(desc) > 100:
            desc = desc[:100] + "..."
        lines.append(f"- actions.{name}(...) - {desc}")

    return "\n".join(lines)




# ==================== SANDBOX ====================

class Sandbox:
    """High-level sandbox for secure Python code execution with MCP tools."""

    def __init__(self, tools_url: str, tools: List[Tool] = None, timeout: int = 60,
                 session_id: str = ""):
        """Initialize the sandbox.

        Args:
            tools_url: SSE URL of the MCP tools server
            tools: Pre-discovered list of Tool objects
            timeout: Default execution timeout in seconds
            session_id: Session ID for DB isolation
        """
        if _CODEMODE_IMPORT_ERROR is not None:
            raise RuntimeError(
                "codemode engine is unavailable because utcp_code_mode failed to import: "
                f"{_CODEMODE_IMPORT_ERROR}"
            )

        self._tools_url = tools_url
        self._tools = tools or []
        self._client = McpToolsClient(tools_url, self._tools, session_id=session_id)
        self._timeout = timeout
        self._session_id = session_id

    def execute(self, code: str, timeout: Optional[int] = None) -> SandboxResult:
        """Execute Python code in the sandbox (synchronous)."""
        start_time = time.time()
        timeout = timeout or self._timeout

        result_container = {"result": None, "error": None}

        def run_async():
            try:
                result_container["result"] = asyncio.run(
                    self._client.call_tool_chain(code, timeout)
                )
            except Exception as e:
                result_container["error"] = e

        thread = threading.Thread(target=run_async)
        thread.start()
        thread.join(timeout=timeout + 5)

        if result_container["error"]:
            return SandboxResult(
                success=False,
                error=str(result_container["error"]),
                logs=[f"[ERROR] {result_container['error']}"],
            )

        if result_container["result"] is None:
            return SandboxResult(
                success=False,
                error=f"Execution timed out after {timeout} seconds",
                logs=[f"[ERROR] Timeout after {timeout}s"],
            )

        cm_result = result_container["result"]
        logs = cm_result.get("logs", [])
        has_error = any("[ERROR]" in str(log) for log in logs)

        return SandboxResult(
            success=not has_error,
            result=cm_result.get("result"),
            output="\n".join(str(log) for log in logs),
            logs=logs,
            error=logs[-1] if has_error and logs else None,
        )


class MontySandbox:
    """Sandbox engine backed by pydantic-monty with MCP tools as external functions."""

    def __init__(self, tools_url: str, tools_map: Dict[str, dict], timeout: int = 60,
                 session_id: str = ""):
        if pydantic_monty is None or _MONTY_IMPORT_ERROR is not None:
            raise RuntimeError(
                "monty engine is unavailable because pydantic_monty failed to import: "
                f"{_MONTY_IMPORT_ERROR}"
            )

        self._tools_url = tools_url
        self._tools_map = tools_map or {}
        self._timeout = timeout
        self._session_id = session_id
        self._client = McpToolsClient(tools_url, [], session_id=session_id)

    @staticmethod
    def _rewrite_actions_calls(code: str) -> str:
        """Adapt common code-mode patterns to Monty-compatible code."""
        rewritten = code
        rewritten = re.sub(r"\bactions\.([A-Za-z_]\w*)(\s*\()", r"\1\2", rewritten)

        # Monty does not currently provide stdlib json import.
        # Convert common patterns to host-provided helpers.
        rewritten = re.sub(r"(?m)^\s*import\s+json\s*$", "", rewritten)
        rewritten = rewritten.replace("json.loads(", "json_loads(")
        rewritten = rewritten.replace("json.dumps(", "json_dumps(")

        return rewritten

    def _build_external_functions(self) -> Dict[str, Callable[..., Any]]:
        external_functions: Dict[str, Callable[..., Any]] = {}

        # Compatibility helpers for code that previously relied on `import json`.
        external_functions["json_loads"] = json.loads
        external_functions["json_dumps"] = json.dumps

        for tool_name, info in self._tools_map.items():
            schema = info.get("parameters", {}) if isinstance(info, dict) else {}
            properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
            param_names = [name for name in properties.keys() if name != "session_id"]

            def _make_tool_fn(name: str, ordered_params: List[str]) -> Callable[..., Any]:
                def _tool_fn(*args, **kwargs):
                    call_kwargs = dict(kwargs)
                    for i, arg in enumerate(args):
                        if i < len(ordered_params):
                            call_kwargs[ordered_params[i]] = arg
                        else:
                            call_kwargs[f"arg{i}"] = arg

                    try:
                        return self._client.call_tool_sync(name, call_kwargs)
                    except RuntimeError:
                        raise
                    except BaseException as error:
                        root_cause = _unwrap_exception(error)
                        raise RuntimeError(f"Error calling tool '{name}': {root_cause}")

                return _tool_fn

            external_functions[tool_name] = _make_tool_fn(tool_name, param_names)

        return external_functions

    def execute(self, code: str, timeout: Optional[int] = None) -> SandboxResult:
        timeout = timeout or self._timeout
        adapted_code = self._rewrite_actions_calls(code)
        logs: List[str] = []

        def _print_cb(_stream: str, text: str) -> None:
            logs.append(text)

        limits = {"max_duration_secs": float(timeout)}

        try:
            runner = pydantic_monty.Monty(adapted_code, script_name="sandbox.py")
            result = runner.run(
                external_functions=self._build_external_functions(),
                print_callback=_print_cb,
                limits=limits,
            )
            return SandboxResult(
                success=True,
                result=result,
                output="".join(logs).rstrip("\n"),
                logs=logs,
                error=None,
            )
        except Exception as error:
            root_cause = _unwrap_exception(error)
            return SandboxResult(
                success=False,
                result=None,
                output="".join(logs).rstrip("\n"),
                logs=logs,
                error=root_cause,
            )


# ==================== BASE DESCRIPTION ====================

EXECUTE_PYTHON_BASE_DESCRIPTION = """Executes Python code in a state-less sandbox environment.

PRINCIPLES FOR SUCCESSFUL TOOL USE:

1. BATCH EVERYTHING (CRITICAL):
   Put ALL actions you can perform right now into ONE script.
   If a user has 5 orders, fetch ALL 5 in ONE call with a loop.
   If you need user + orders + products, get ALL in ONE call.
   Each separate execute_python call wastes a turn. Minimize total calls.

2. STATELESS: Variables do NOT persist between calls.

3. NO GUESSING: NEVER guess emails, IDs, or names. Ask the user if missing.

4. PRINT DATA: print() is the ONLY way to see output. Use bare print(x).

5. NO input(): Never use input() or reference input/Input/user_input.

6. DIRECT DICT ACCESS: All actions.* return dicts. No json.loads().

7. MINIMAL CODE: Zero comments. Short var names. No f-string labels.

EXAMPLE — auth + user + ALL orders in one call:
```python
uid = actions.find_user_id_by_name_zip("First", "Last", "12345")
u = actions.get_user_details(uid)
print(u)
for oid in u['orders']:
    print(actions.get_order_details(oid))
```

API REFERENCE:
The `actions` object is pre-loaded with these methods:
"""

EXECUTE_PYTHON_BASE_DESCRIPTION_MONTY = """Executes Python code in a state-less sandbox environment.

PRINCIPLES FOR SUCCESSFUL TOOL USE:

1. STATELESS EXECUTION (CRITICAL):
    This environment does NOT preserve variables between turns.
    You MUST redefine all variables or use string literals in every block.

2. GROUND TRUTH ONLY (NO GUESSING):
    NEVER guess IDs, emails, names, or account values.

3. PRINT EVERYTHING:
    This tool only returns what you explicitly `print()`.

4. INPUT BAN (HIGHEST PRIORITY):
     - Never use `input()`.

5. MONTY COMPATIBILITY:
     - Do NOT use `import json` in code.
     - Use `json_loads(...)` and `json_dumps(...)` helper functions instead.

EXAMPLE:
```python
result = actions.some_method("arg")
print(result)
```

SAFE EXECUTION TEMPLATE:
```python
raw = actions.some_method("arg")
data = json_loads(raw) if isinstance(raw, str) and raw[:1] in '{[' else raw
print(type(data), data)
```

API REFERENCE:
The `actions` object is pre-loaded with these methods:
          """

# ==================== MCP SERVER ====================

# Create the MCP server
mcp = FastMCP(
    "Code Sandbox Server",
    instructions="""You are a Python coding agent for customer service tasks.
Execute Python code to help customers using the connected tools server.

Use the execute_python tool with code that calls actions.method_name() to interact with the current domain.
For example: actions.method_name(...)"""
)

# Global state
_tools_url: Optional[str] = None
_available_tools: Dict[str, dict] = {}  # tool_name -> {description, parameters}
_utcp_tools: List[Tool] = []  # UTCP Tool objects for code-mode sandbox
_session_id: str = ""  # Stable session ID for DB isolation (set once at startup)
_flowise_chat_id: str = ""  # chatId explicitly registered via get_session_id
_session_lock = threading.Lock()
_tools_refresh_lock = threading.Lock()
_tools_refresh_interval_sec = 10
_last_tools_refresh_ts = 0.0
_last_tools_refresh_error = ""
_tools_watcher_started = False
_current_execute_python_description = ""
_registered_core_tools = False
_execution_engine = "codemode"


def _as_non_empty_str(value: Any) -> str:
    """Normalize a candidate session value to a non-empty string."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"none", "null"}:
        return ""
    return text


def _set_flowise_chat_id(chat_id: str) -> str:
    """Persist the latest Flowise chatId for execute_python session routing."""
    normalized = _as_non_empty_str(chat_id)
    if not normalized:
        return ""
    with _session_lock:
        global _flowise_chat_id
        _flowise_chat_id = normalized
    return normalized


def _get_effective_session_id() -> Tuple[str, str]:
    """Resolve session id strictly from get_session_id chatId, with startup fallback."""
    with _session_lock:
        chat_id = _flowise_chat_id
    if chat_id:
        return chat_id, "flowise-chat-id"
    return _session_id, "startup-fallback"


def _build_execute_python_description() -> str:
    """Build the current execute_python description from discovered tools + metadata."""
    tool_metadata: Dict[str, Any] = {}
    if _tools_url:
        tool_metadata = asyncio.run(_fetch_remote_tool_metadata(_tools_url, _session_id))

    metadata_full_desc = ""
    if tool_metadata:
        maybe_desc = tool_metadata.get("execute_python_description", "")
        if isinstance(maybe_desc, str):
            metadata_full_desc = maybe_desc

    if metadata_full_desc:
        logger.info("Using metadata-provided execute_python description for exact parity")
        return metadata_full_desc

    actions_desc = _generate_dynamic_description(_available_tools, tool_metadata)
    base = (
        EXECUTE_PYTHON_BASE_DESCRIPTION_MONTY
        if _execution_engine == "monty"
        else EXECUTE_PYTHON_BASE_DESCRIPTION
    )
    return base + "\n" + actions_desc


def _upsert_execute_python_tool(reason: str = "") -> None:
    """Register or update execute_python tool description if changed."""
    global _current_execute_python_description

    if not _available_tools:
        return

    new_desc = _build_execute_python_description()
    if not new_desc:
        return

    if _current_execute_python_description == new_desc:
        return

    try:
        mcp.remove_tool("execute_python")
    except Exception:
        pass

    mcp.tool(
        name="execute_python",
        description=new_desc,
        exclude_args=["ctx"],
    )(execute_python)

    # Inject Pydantic-style title fields into the schema to match tau2-bench
    # exactly. tau2 uses Pydantic openai_schema which adds "title" fields;
    # FastMCP strips them by default.
    try:
        tool_obj = mcp._tool_manager._tools.get("execute_python")
        if tool_obj and hasattr(tool_obj, "parameters"):
            tool_obj.parameters.setdefault("title", "parameters")
            code_prop = tool_obj.parameters.get("properties", {}).get("code")
            if code_prop is not None:
                code_prop.setdefault("title", "Code")
    except Exception:
        pass  # Non-critical — only affects template title tags

    _current_execute_python_description = new_desc
    logger.info(
        "Registered/updated execute_python tool description (%s, %d chars)",
        reason or "refresh",
        len(new_desc),
    )
    logger.info("===== BEGIN execute_python DESCRIPTION (%s) =====", reason or "refresh")
    logger.info("%s", new_desc)
    logger.info("===== END execute_python DESCRIPTION =====")


def _register_core_tools() -> None:
    """Register core sandbox tools once."""
    global _registered_core_tools
    if _registered_core_tools:
        return
    mcp.tool(
        name="get_session_id",
        description="Set the runtime session id from Flowise chatId and return it as JSON.",
    )(get_session_id_from_flowise)
    _registered_core_tools = True
    logger.info("Registered get_session_id tool for Flowise chat/session bootstrap")


def _refresh_tools_cache(force: bool = False, reason: str = "") -> bool:
    """Refresh tool discovery cache from tools-server.

    This is resilient by design:
    - If discovery fails, keep existing cached tools.
    - If discovery returns empty, keep existing cached tools.
    """
    global _utcp_tools, _available_tools, _last_tools_refresh_ts, _last_tools_refresh_error

    if not _tools_url:
        return False

    now = time.time()
    if not force and _utcp_tools and (now - _last_tools_refresh_ts) < _tools_refresh_interval_sec:
        return True

    with _tools_refresh_lock:
        now = time.time()
        if not force and _utcp_tools and (now - _last_tools_refresh_ts) < _tools_refresh_interval_sec:
            return True

        try:
            discovered_utcp = asyncio.run(discover_mcp_tools(_tools_url))
            discovered_flat = asyncio.run(discover_tools(_tools_url))

            if discovered_utcp:
                _utcp_tools = discovered_utcp
            if discovered_flat:
                _available_tools = discovered_flat

            if discovered_utcp or discovered_flat:
                _last_tools_refresh_ts = now
                _last_tools_refresh_error = ""
                _upsert_execute_python_tool(reason=reason or "refresh")
                logger.info(
                    "Refreshed tools cache (%s): utcp=%d, flat=%d",
                    reason or "refresh",
                    len(_utcp_tools),
                    len(_available_tools),
                )
                return True

            _last_tools_refresh_error = "no tools discovered"
            if _utcp_tools:
                return True
            logger.warning("Tool refresh returned no tools (%s)", reason or "refresh")
            return False
        except Exception as exc:
            _last_tools_refresh_error = str(exc)
            if _utcp_tools:
                logger.warning(
                    "Tool refresh failed (%s), keeping cached tools: %s",
                    reason or "refresh",
                    exc,
                )
                return True
            logger.warning("Tool refresh failed (%s): %s", reason or "refresh", exc)
            return False


def _start_tools_watcher() -> None:
    """Background watcher that keeps trying to refresh tool cache."""
    global _tools_watcher_started
    if _tools_watcher_started:
        return

    def _worker() -> None:
        while True:
            _refresh_tools_cache(force=False, reason="background")
            time.sleep(_tools_refresh_interval_sec)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    _tools_watcher_started = True
    logger.info("Started tools watcher (interval=%ss)", _tools_refresh_interval_sec)


def get_session_id_from_flowise(sessionId: str = "", chatId: str = "", ctx: Context = None) -> str:
    """Store Flowise chatId and return it as the only runtime session id."""
    _ = sessionId
    _ = ctx
    chat_id_value = _as_non_empty_str(chatId)

    if not chat_id_value:
        logger.warning("get_session_id called without chatId; keeping previous session id")
        payload = {
            "ok": False,
            "error": "chatId is required",
            "session_id": _flowise_chat_id or _session_id,
            "chat_id": _flowise_chat_id,
            "source": "flowise-bootstrap",
        }
        return json.dumps(payload)

    effective_id = _set_flowise_chat_id(chat_id_value)

    payload = {
        "ok": True,
        "session_id": effective_id,
        "chat_id": effective_id,
        "source": "flowise-bootstrap",
    }
    logger.info(
        "Flowise session bootstrap: sessionId=%s, chatId=%s -> using=%s",
        sessionId,
        chatId,
        effective_id,
    )
    return json.dumps(payload)

def execute_python(
    code: str = "",
    ctx: Optional[Context] = None,
) -> str:
    """Execute Python code with access to tools via the actions object."""
    _ = ctx

    if _execution_engine == "codemode":
        if not _utcp_tools:
            _refresh_tools_cache(force=True, reason="execute_python")

        if not _utcp_tools:
            return (
                "[ERROR] Connected tools are not available yet. "
                "Sandbox is waiting for tools-server at the configured --tools-url. "
                "Please retry in a few seconds."
            )
    else:
        if not _available_tools:
            _refresh_tools_cache(force=True, reason="execute_python")

        if not _available_tools:
            return (
                "[ERROR] Connected tools are not available yet. "
                "Sandbox is waiting for tools-server at the configured --tools-url. "
                "Please retry in a few seconds."
            )

    session_id, session_source = _get_effective_session_id()

    logger.info(f"========================================")
    logger.info(
        f"Engine: {_execution_engine} | Session: {session_id[:12]}... ({session_source}) | Executing code ({len(code)} chars)"
    )
    logger.info(f"========================================")

    if not code:
        return "Error: No code provided. Please provide the python code to execute in the 'code' argument."

    # Create a per-request sandbox with the session ID for DB isolation
    if _execution_engine == "codemode":
        sandbox = Sandbox(
            tools_url=_tools_url,
            tools=_utcp_tools,
            session_id=session_id,
        )
    else:
        sandbox = MontySandbox(
            tools_url=_tools_url,
            tools_map=_available_tools,
            session_id=session_id,
        )

    try:
        result = sandbox.execute(code)

        output_parts = []

        # Collect printed output (excluding [ERROR] lines to avoid duplication)
        if result.output:
            clean_output = "\n".join(
                line for line in result.output.splitlines()
                if not line.strip().startswith("[ERROR]")
            ).strip()
            if clean_output:
                output_parts.append(clean_output)

        if not result.success:
            # Extract the core error message, stripping repeated "Code execution failed:" prefixes
            error_msg = result.error or "Unknown error"
            while "Code execution failed: Code execution failed:" in error_msg:
                error_msg = error_msg.replace("Code execution failed: Code execution failed:",
                                              "Code execution failed:", 1)
            # Also strip the [ERROR] prefix if the library added it
            error_msg = error_msg.lstrip("[ERROR] ").strip()
            # Strip one remaining "Code execution failed: " to get to the root cause
            if error_msg.startswith("Code execution failed: "):
                error_msg = error_msg[len("Code execution failed: "):]

            # Add SYSTEM HINT if not already present
            if "SYSTEM HINT:" not in error_msg:
                hint = _analyze_error_message_with_tools(error_msg, code, session_id=session_id)
                if hint:
                    error_msg += f"\n\nSYSTEM HINT: {hint}"
            output_parts.append(f"[ERROR] {error_msg}")

        return "\n".join(output_parts) if output_parts else "(no output)"

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Execution failed: {e}\n{tb}")
        # Extract root cause
        root_msg = _unwrap_exception(e)
        hint = _analyze_error_message_with_tools(root_msg, code, session_id=session_id)
        error_output = f"[ERROR] {root_msg}"
        if hint:
            error_output += f"\n\nSYSTEM HINT: {hint}"
        return error_output


@mcp.tool()
def list_available_actions() -> str:
    """List all available actions from the connected tools server.

    Returns:
        A list of available action methods and their descriptions.
    """
    if not _available_tools:
        _refresh_tools_cache(force=True, reason="list_available_actions")
    return get_tools_documentation(_available_tools)


def main():
    global _tools_url, _available_tools, _utcp_tools, _session_id, _execution_engine

    parser = argparse.ArgumentParser(description="MCP Sandbox Server (Code-Mode/Monty)")
    parser.add_argument("--port", type=int, default=5051, help="Port to listen on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--tools-url", required=True, help="URL of MCP tools server (SSE)")
    parser.add_argument(
        "--engine",
        choices=["codemode", "monty"],
        default="codemode",
        help="Python execution engine to use (default: codemode)",
    )
    parser.add_argument("--session-id", default="",
                        help="Fixed session ID for DB isolation. "
                             "If empty (default), auto-generates one at startup. "
                             "All execute_python calls share this single session. "
                             "Restart the server to get a fresh DB.")
    args = parser.parse_args()

    _tools_url = args.tools_url
    _execution_engine = args.engine

    if _execution_engine == "codemode" and _CODEMODE_IMPORT_ERROR is not None:
        raise RuntimeError(
            "codemode engine selected but utcp_code_mode is unavailable: "
            f"{_CODEMODE_IMPORT_ERROR}"
        )
    if _execution_engine == "monty" and _MONTY_IMPORT_ERROR is not None:
        raise RuntimeError(
            "monty engine selected but pydantic_monty is unavailable: "
            f"{_MONTY_IMPORT_ERROR}"
        )

    # Set up stable session ID (one per server lifetime)
    if args.session_id:
        _session_id = args.session_id
    else:
        _session_id = str(uuid4())
    logger.info(f"Execution engine: {_execution_engine}")
    logger.info(f"Session ID: {_session_id[:12]}... (all calls share this DB session)")

    # Initial discovery (non-fatal if tools-server is not up yet)
    logger.info(f"Discovering tools from {_tools_url}...")
    _refresh_tools_cache(force=True, reason="startup")
    logger.info(f"Discovered {len(_utcp_tools)} UTCP tools")
    for tool in sorted(_utcp_tools, key=lambda t: t.name):
        logger.info(f"  - {tool.name}")

    logger.info(f"Discovered {len(_available_tools)} tools for description")
    for name in sorted(_available_tools.keys()):
        logger.info(f"  - {name}")

    _register_core_tools()
    _upsert_execute_python_tool(reason="startup")

    # Keep sandbox running and auto-recover when tools-server appears/restarts.
    _start_tools_watcher()

    # Run the MCP server
    logger.info(f"Starting MCP sandbox server on {args.host}:{args.port}")
    mcp.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
