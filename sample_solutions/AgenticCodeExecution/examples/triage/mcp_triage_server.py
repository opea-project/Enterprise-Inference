#!/usr/bin/env python3
"""
MCP Server for Incident Triage Tools - Fully Standalone

This domain is intentionally non-DB-centric and focused on chainable operational checks.
"""

import argparse
import json
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastmcp import FastMCP

# Add parent directory to sys.path for shared modules (error_hints)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from error_hints import analyze_execution_error


mcp = FastMCP(
    "Incident Triage Tools Server",
    instructions="""You are an incident triage support agent. Use these tools to help users with:
- Checking HTTP endpoint health and latency
- Resolving DNS and testing TCP connectivity
- Inspecting TLS certificate metadata
- Checking public vendor status pages
- Building structured triage summaries and customer updates

Always gather evidence first, then summarize impact, likely cause, and next steps.""",
)


_STATUS_APIS = {
    "github": "https://www.githubstatus.com/api/v2/status.json",
    "openai": "https://status.openai.com/api/v2/status.json",
    "cloudflare": "https://www.cloudflarestatus.com/api/v2/status.json",
    "slack": "https://status.slack.com/api/v2.0.0/current",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _http_get_json(url: str, timeout_sec: int = 8) -> Dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "mcp-triage-server/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_sec) as response:
        body = response.read().decode("utf-8", errors="replace")
        return json.loads(body)


def _safe_json_loads(raw: str, default: Any) -> Any:
    try:
        return json.loads(raw)
    except Exception:
        return default


def _severity_rank(severity: str) -> int:
    order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    return order.get((severity or "").strip().lower(), 0)


def _infer_severity(http_ok: bool, tcp_ok: bool, vendor_indicator: str, error_text: str) -> str:
    text = (error_text or "").lower()
    if (not tcp_ok and not http_ok) or "outage" in vendor_indicator.lower() or "critical" in text:
        return "critical"
    if (not http_ok) or "major" in vendor_indicator.lower() or "timeout" in text:
        return "high"
    if "degraded" in vendor_indicator.lower() or "latency" in text or "error" in text:
        return "medium"
    return "low"


@mcp.tool()
def check_http_endpoint(url: str, timeout_sec: int = 8, session_id: str = "") -> str:
    """Check HTTP endpoint health and latency.

    Args:
        url: Endpoint URL, such as 'https://api.example.com/health'.
        timeout_sec: Timeout in seconds.

    Returns:
        A JSON STRING with status_code, latency_ms, ok flag, and response snippet.
    """
    _ = session_id
    start = time.perf_counter()
    request = urllib.request.Request(url, headers={"User-Agent": "mcp-triage-server/1.0"})

    result: Dict[str, Any] = {
        "url": url,
        "checked_at": _now_iso(),
        "ok": False,
        "status_code": None,
        "latency_ms": None,
        "error": None,
        "response_excerpt": "",
    }

    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            body = response.read(400).decode("utf-8", errors="replace")
            result.update(
                {
                    "ok": 200 <= int(response.status) < 400,
                    "status_code": int(response.status),
                    "latency_ms": elapsed_ms,
                    "response_excerpt": body,
                }
            )
    except urllib.error.HTTPError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        body = exc.read(400).decode("utf-8", errors="replace") if exc.fp else ""
        result.update(
            {
                "ok": False,
                "status_code": int(exc.code),
                "latency_ms": elapsed_ms,
                "error": str(exc),
                "response_excerpt": body,
            }
        )
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        result.update({"latency_ms": elapsed_ms, "error": str(exc)})

    return json.dumps(result, indent=2)


@mcp.tool()
def run_latency_probe(url: str, attempts: int = 3, timeout_sec: int = 6, session_id: str = "") -> str:
    """Run repeated HTTP checks to estimate latency stability.

    Args:
        url: Endpoint URL.
        attempts: Number of probe attempts (1-10).
        timeout_sec: Timeout per request.

    Returns:
        A JSON STRING with per-attempt latencies and summary stats.
    """
    _ = session_id
    attempts = max(1, min(10, int(attempts)))
    samples: List[float] = []
    statuses: List[int] = []
    errors: List[str] = []

    for _idx in range(attempts):
        parsed = _safe_json_loads(check_http_endpoint(url=url, timeout_sec=timeout_sec), {})
        latency = parsed.get("latency_ms")
        if isinstance(latency, (int, float)):
            samples.append(float(latency))
        status_code = parsed.get("status_code")
        if isinstance(status_code, int):
            statuses.append(status_code)
        if parsed.get("error"):
            errors.append(str(parsed.get("error")))

    summary = {
        "url": url,
        "attempts": attempts,
        "latencies_ms": samples,
        "min_ms": min(samples) if samples else None,
        "max_ms": max(samples) if samples else None,
        "avg_ms": round(sum(samples) / len(samples), 2) if samples else None,
        "status_codes": statuses,
        "errors": errors,
        "checked_at": _now_iso(),
    }
    return json.dumps(summary, indent=2)


@mcp.tool()
def resolve_hostname(hostname: str, session_id: str = "") -> str:
    """Resolve hostname to IPv4/IPv6 addresses.

    Args:
        hostname: Hostname such as 'api.example.com'.

    Returns:
        A JSON STRING with resolved addresses.
    """
    _ = session_id
    records = socket.getaddrinfo(hostname, None)
    addresses = sorted({rec[4][0] for rec in records})
    return json.dumps(
        {
            "hostname": hostname,
            "resolved_addresses": addresses,
            "count": len(addresses),
            "checked_at": _now_iso(),
        },
        indent=2,
    )


@mcp.tool()
def check_tcp_port(host: str, port: int, timeout_sec: int = 4, session_id: str = "") -> str:
    """Check TCP connectivity to a host and port.

    Args:
        host: Target hostname or IP.
        port: TCP port.
        timeout_sec: Timeout in seconds.

    Returns:
        A JSON STRING with connectivity result and latency.
    """
    _ = session_id
    start = time.perf_counter()
    result = {
        "host": host,
        "port": int(port),
        "ok": False,
        "latency_ms": None,
        "error": None,
        "checked_at": _now_iso(),
    }

    try:
        with socket.create_connection((host, int(port)), timeout=timeout_sec):
            result["ok"] = True
            result["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
    except Exception as exc:
        result["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
        result["error"] = str(exc)

    return json.dumps(result, indent=2)


@mcp.tool()
def inspect_tls_certificate(host: str, port: int = 443, timeout_sec: int = 5, session_id: str = "") -> str:
    """Inspect basic TLS certificate metadata for a host.

    Args:
        host: Target hostname.
        port: TLS port (default 443).
        timeout_sec: Timeout in seconds.

    Returns:
        A JSON STRING with cert subject, issuer, and validity dates.
    """
    _ = session_id
    context = ssl.create_default_context()
    with socket.create_connection((host, int(port)), timeout=timeout_sec) as sock:
        with context.wrap_socket(sock, server_hostname=host) as tls_sock:
            cert = tls_sock.getpeercert()

    def _flatten_name(name_items: List[Any]) -> Dict[str, str]:
        flattened: Dict[str, str] = {}
        for item in name_items:
            for key, value in item:
                flattened[key] = value
        return flattened

    data = {
        "host": host,
        "port": int(port),
        "subject": _flatten_name(cert.get("subject", [])),
        "issuer": _flatten_name(cert.get("issuer", [])),
        "not_before": cert.get("notBefore"),
        "not_after": cert.get("notAfter"),
        "serial_number": cert.get("serialNumber"),
        "checked_at": _now_iso(),
    }
    return json.dumps(data, indent=2)


@mcp.tool()
def get_public_status(service: str, timeout_sec: int = 8, session_id: str = "") -> str:
    """Get public status from a known vendor status API.

    Args:
        service: One of 'github', 'openai', 'cloudflare', 'slack'.
        timeout_sec: Request timeout in seconds.

    Returns:
        A JSON STRING with normalized status indicator and description.
    """
    _ = session_id
    key = service.strip().lower()
    if key not in _STATUS_APIS:
        raise ValueError("Unsupported service. Choose: github, openai, cloudflare, slack")

    url = _STATUS_APIS[key]
    payload = _http_get_json(url, timeout_sec=timeout_sec)

    indicator = "unknown"
    description = ""

    if key == "slack":
        status = payload.get("status", "").lower()
        if status in {"active", "ok"}:
            indicator = "none"
            description = "All systems operational"
        elif status:
            indicator = status
            description = payload.get("date_updated", "")
    else:
        page_status = payload.get("status", {})
        indicator = page_status.get("indicator", "unknown")
        description = page_status.get("description", "")

    return json.dumps(
        {
            "service": key,
            "status_api": url,
            "indicator": indicator,
            "description": description,
            "checked_at": _now_iso(),
            "raw": payload,
        },
        indent=2,
    )


@mcp.tool()
def summarize_incident_signals(
    service_name: str,
    http_result_json: str = "",
    tcp_result_json: str = "",
    public_status_json: str = "",
    error_text: str = "",
    session_id: str = "",
) -> str:
    """Summarize triage signals into severity, likely cause, and recommended next steps.

    Args:
        service_name: Name of affected service.
        http_result_json: JSON string from check_http_endpoint/run_latency_probe.
        tcp_result_json: JSON string from check_tcp_port.
        public_status_json: JSON string from get_public_status.
        error_text: Additional observed error text/log snippet.

    Returns:
        A JSON STRING triage summary with severity and recommended actions.
    """
    _ = session_id
    http_data = _safe_json_loads(http_result_json, {})
    tcp_data = _safe_json_loads(tcp_result_json, {})
    vendor_data = _safe_json_loads(public_status_json, {})

    http_ok = bool(http_data.get("ok", False))
    tcp_ok = bool(tcp_data.get("ok", False))
    vendor_indicator = str(vendor_data.get("indicator", ""))

    severity = _infer_severity(http_ok=http_ok, tcp_ok=tcp_ok, vendor_indicator=vendor_indicator, error_text=error_text)

    likely_causes: List[str] = []
    if not tcp_ok:
        likely_causes.append("Network path or service port is unreachable")
    if tcp_ok and not http_ok:
        likely_causes.append("Application layer issue (5xx/4xx, timeout, or upstream dependency)")
    if vendor_indicator and vendor_indicator not in {"none", "unknown", "active", "ok"}:
        likely_causes.append(f"Upstream provider incident indicated by status API: {vendor_indicator}")
    if not likely_causes:
        likely_causes.append("No hard failure detected; investigate intermittent latency or client-side issues")

    recommended_actions = [
        "Validate blast radius across regions/endpoints",
        "Compare current error rate vs baseline",
        "Check recent deployments/config changes",
        "Notify stakeholders with next update ETA",
    ]

    if not tcp_ok:
        recommended_actions.insert(0, "Escalate to network/infrastructure on-call")
    elif not http_ok:
        recommended_actions.insert(0, "Inspect application logs and upstream dependency health")

    summary = {
        "service_name": service_name,
        "severity": severity,
        "signals": {
            "http_ok": http_ok,
            "http_status_code": http_data.get("status_code"),
            "tcp_ok": tcp_ok,
            "vendor_indicator": vendor_indicator,
            "error_text": error_text,
        },
        "likely_causes": likely_causes,
        "recommended_actions": recommended_actions,
        "generated_at": _now_iso(),
    }
    return json.dumps(summary, indent=2)


@mcp.tool()
def create_incident_report(
    service_name: str,
    severity: str,
    impact_summary: str,
    findings: str,
    next_actions: str,
    session_id: str = "",
) -> str:
    """Create a structured incident report object from triage findings.

    Args:
        service_name: Affected service name.
        severity: low|medium|high|critical.
        impact_summary: Human-readable impact statement.
        findings: JSON or plain-text findings summary.
        next_actions: JSON array string or plain-text next actions.

    Returns:
        A JSON STRING incident report with generated incident_id.
    """
    _ = session_id
    sev = (severity or "").strip().lower()
    if sev not in {"low", "medium", "high", "critical"}:
        raise ValueError("severity must be one of: low, medium, high, critical")

    findings_obj = _safe_json_loads(findings, findings)
    actions_obj = _safe_json_loads(next_actions, [next_actions])
    if isinstance(actions_obj, str):
        actions_obj = [actions_obj]

    ts = datetime.now(timezone.utc)
    incident_id = f"INC-{ts.strftime('%Y%m%d-%H%M%S')}"

    report = {
        "incident_id": incident_id,
        "service_name": service_name,
        "severity": sev,
        "severity_rank": _severity_rank(sev),
        "status": "investigating",
        "impact_summary": impact_summary,
        "findings": findings_obj,
        "next_actions": actions_obj,
        "created_at": _now_iso(),
    }
    return json.dumps(report, indent=2)


@mcp.tool()
def draft_customer_update(
    service_name: str,
    severity: str,
    impact_summary: str,
    current_status: str,
    next_update_eta_minutes: int = 30,
    session_id: str = "",
) -> str:
    """Draft a concise customer-facing status update.

    Args:
        service_name: Affected service name.
        severity: low|medium|high|critical.
        impact_summary: Customer impact summary.
        current_status: Current mitigation/investigation status.
        next_update_eta_minutes: ETA for next update.

    Returns:
        A plain-text status update message.
    """
    _ = session_id
    sev = (severity or "").strip().lower()
    eta = max(5, int(next_update_eta_minutes))

    message = (
        f"Incident Update ({service_name})\n"
        f"Severity: {sev.upper()}\n"
        f"Impact: {impact_summary}\n"
        f"Current Status: {current_status}\n"
        f"Next Update: in approximately {eta} minutes."
    )
    return message


@mcp.tool()
def calculate(expression: str, session_id: str = "") -> str:
    """Calculate the result of a mathematical expression."""
    _ = session_id
    if not all(char in "0123456789+-*/(). " for char in expression):
        raise ValueError("Invalid characters in expression")
    return str(round(float(eval(expression, {"__builtins__": None}, {})), 6))


@mcp.tool()
def transfer_to_human_agents(summary: str, session_id: str = "") -> str:
    """Transfer the customer to a human incident commander/on-call engineer."""
    _ = summary
    _ = session_id
    return "Transfer successful"


def _get_data_model_defs() -> Dict[str, dict]:
    return {
        "HealthCheck": {
            "description": "HTTP health check result",
            "properties": {
                "url": {"type": "string"},
                "ok": {"type": "boolean"},
                "status_code": {"type": "integer"},
                "latency_ms": {"type": "number"},
                "error": {"type": "string"},
            },
        },
        "IncidentSummary": {
            "description": "Machine-readable triage summary",
            "properties": {
                "service_name": {"type": "string"},
                "severity": {"type": "string"},
                "likely_causes": {"type": "array"},
                "recommended_actions": {"type": "array"},
            },
        },
        "IncidentReport": {
            "description": "Structured incident ticket/report payload",
            "properties": {
                "incident_id": {"type": "string"},
                "service_name": {"type": "string"},
                "severity": {"type": "string"},
                "status": {"type": "string"},
                "impact_summary": {"type": "string"},
                "findings": {"type": "object"},
                "next_actions": {"type": "array"},
            },
        },
    }


def _get_tool_metadata_payload() -> Dict[str, Any]:
    ordered_actions = [
        "check_http_endpoint",
        "run_latency_probe",
        "resolve_hostname",
        "check_tcp_port",
        "inspect_tls_certificate",
        "get_public_status",
        "summarize_incident_signals",
        "create_incident_report",
        "draft_customer_update",
        "calculate",
        "transfer_to_human_agents",
    ]

    return {
        "ordered_actions": ordered_actions,
        "return_types": {
            "check_http_endpoint": "str (JSON)",
            "run_latency_probe": "str (JSON)",
            "resolve_hostname": "str (JSON)",
            "check_tcp_port": "str (JSON)",
            "inspect_tls_certificate": "str (JSON)",
            "get_public_status": "str (JSON)",
            "summarize_incident_signals": "str (JSON)",
            "create_incident_report": "str (JSON)",
            "draft_customer_update": "str",
            "calculate": "str",
            "transfer_to_human_agents": "str",
        },
        "semantic_types": {
            "check_http_endpoint": "HealthCheck",
            "run_latency_probe": "dict[latency_stats]",
            "resolve_hostname": "dict[hostname_resolution]",
            "check_tcp_port": "dict[tcp_connectivity]",
            "inspect_tls_certificate": "dict[tls_certificate]",
            "get_public_status": "dict[provider_status]",
            "summarize_incident_signals": "IncidentSummary",
            "create_incident_report": "IncidentReport",
        },
        "data_model_defs": _get_data_model_defs(),
    }


@mcp.tool()
def get_execution_error_hint(error_msg: str, code: str = "", session_id: str = "") -> str:
    """Return a recovery hint for sandbox execution/tool errors."""
    _ = session_id
    return analyze_execution_error(error_msg=error_msg, code=code, domain="triage")


@mcp.tool()
def get_tool_metadata(session_id: str = "") -> str:
    """Return metadata used to build execute_python action/data-model description."""
    _ = session_id
    return json.dumps(_get_tool_metadata_payload())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Incident Triage MCP Server")
    parser.add_argument("--port", type=int, default=5050, help="Port to run the SSE server on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument(
        "--transport",
        choices=["sse", "stdio"],
        default="sse",
        help="Transport protocol to use",
    )

    args = parser.parse_args()

    print("\n🚀 Starting Incident Triage MCP Server...")
    print(f"   Transport: {args.transport}")
    if args.transport == "sse":
        print(f"   Host: {args.host}")
        print(f"   Port: {args.port}")
        print(f"   SSE endpoint: http://{args.host}:{args.port}/sse")

    mcp.run(transport=args.transport, host=args.host, port=args.port)
