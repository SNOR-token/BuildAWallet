"""Read-only discovery for the wallet design preview. No live agent execution."""
from __future__ import annotations
from mcp.server import MCPServer
from chains import public_registry

mcp = MCPServer(
    "Build-a-Wallet",
    instructions=(
        "Wallet design preview. Production agent wallets, signing and REST /v1 are not deployed."
    ),
)

@mcp.tool()
def capabilities() -> dict:
    """Describe preview status without advertising a live agent wallet."""
    return {
        "protocol":"Build-a-Wallet Agent Protocol",
        "version":"1.0.0-alpha.7",
        "status":"preview",
        "network":"none",
        "agent_api":"not deployed",
        "transaction_signing":False,
        "broadcast":False,
        "planned_chains":[x["id"] for x in public_registry()],
    }

@mcp.tool()
def chains() -> dict:
    """List planned chains, not live mainnet integrations."""
    return {"network":"none","planned_chains":[x["id"] for x in public_registry()]}

@mcp.resource("baw://policy-model")
def policy_model() -> str:
    """Describe the agent authority policy model."""
    return (
        "Proposed policies constrain actions, assets, destinations, spend and approvals. "
        "The public server does not create wallets, sign or broadcast transactions."
    )

mcp_app = mcp.streamable_http_app()
