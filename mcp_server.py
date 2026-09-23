"""Operational MCP server for Build-a-Wallet.
Read-oriented tools expose capabilities and chain registry. Mutating wallet actions remain on the authenticated REST API so the same policy/approval boundary is not bypassed.
"""
from __future__ import annotations
from mcp.server import MCPServer
from chains import public_registry

mcp = MCPServer(
    "Build-a-Wallet",
    instructions=(
        "Wallet infrastructure for autonomous agents. Humans define policy; agents operate within scoped authority. "
        "Use REST /v1 for authenticated wallet creation, transaction requests, approvals and execution."
    ),
)

@mcp.tool()
def capabilities() -> dict:
    """Describe Build-a-Wallet execution and security capabilities."""
    return {
        "protocol":"Build-a-Wallet Agent Protocol",
        "version":"1.0.0-alpha.7",
        "network":"mainnet",
        "chains":[x["id"] for x in public_registry()],
        "rest_api":"/v1",
        "openapi":"/openapi.json",
        "security":["scoped_credentials","operator_separation","policy_limits","audit_log","broadcast_kill_switch"],
    }

@mcp.tool()
def chains() -> dict:
    """List supported mainnet chains and whether their RPC is configured."""
    return {"network":"mainnet","chains":public_registry()}

@mcp.resource("baw://policy-model")
def policy_model() -> str:
    """Describe the agent authority policy model."""
    return (
        "Policies can constrain allowed actions/assets/destinations, maximum transaction USD value, "
        "daily spend, human-approval thresholds and authority expiration. Pricing is determined server-side."
    )

mcp_app = mcp.streamable_http_app()
