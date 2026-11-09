"""Model Context Protocol (MCP) server for AeroSTE-Core."""

import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from app.engine import evaluate_ste_metrics, compute_h3_spatial_tensor

# Initialize MCP Server
mcp = FastMCP("AeroSTE-Core")

REPO_ROOT = Path(__file__).parent


@mcp.tool()
def evaluate_text_compliance(
    text_payload: str,
    profile: str = "general",
    lat: float = 2.27,
    lon: float = 102.55,
    window_steps: int = 10,
) -> dict:
    """Analyze and score text deterministically for clarity and controlled English compliance.

    Args:
        text_payload: The raw text or operational instruction to evaluate.
        profile: Strictness tier ('general', 'technical', or 'aerospace_ste').
        lat: Latitude coordinate for field operational context.
        lon: Longitude coordinate for field operational context.
        window_steps: Observation telemetry steps (1 to 100).
    """
    return evaluate_ste_metrics({
        "text_payload": text_payload,
        "profile": profile,
        "lat": lat,
        "lon": lon,
        "window_steps": window_steps,
    })


@mcp.tool()
def get_spatial_hangar_density(lat: float, lon: float, resolution: int = 8) -> dict:
    """Resolve coordinates to an Uber H3 cell index and calculate localized MRO density.

    Args:
        lat: Target latitude.
        lon: Target longitude.
        resolution: Uber H3 spatial resolution index (0 to 15, default: 8).
    """
    return compute_h3_spatial_tensor(lat=lat, lon=lon, resolution=resolution)


@mcp.resource("ste://rules")
def get_ste_rules() -> str:
    """Expose the ASD-STE100 mechanical syntax boundaries and word ceilings."""
    rules_file = REPO_ROOT / "rules" / "rules.md"
    if rules_file.exists():
        return rules_file.read_text(encoding="utf-8")
    return "Error: rules.md file not found."


@mcp.resource("ste://vocabulary")
def get_ste_vocabulary() -> str:
    """Expose the complete ASD-STE100 term substitution dictionary matrix."""
    vocab_file = REPO_ROOT / "rules" / "vocabulary.md"
    if vocab_file.exists():
        return vocab_file.read_text(encoding="utf-8")
    return "Error: vocabulary.md file not found."


if __name__ == "__main__":
    mcp.run(transport="stdio")
