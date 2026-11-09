"""FastAPI operational service for text clarity evaluation, technical documentation, and ASD-STE100 compliance."""

from typing import Any, Dict, Optional
from fastapi import FastAPI, Body
from pydantic import BaseModel, Field

from app.engine import evaluate_ste_metrics, compute_h3_spatial_tensor

app = FastAPI(
    title="AeroSTE-Core",
    version="1.1.0",
    description="Multi-tier text clarity, technical documentation, and ASD-STE100 compliance engine with geospatial telemetry.",
)


class ComplianceRequest(BaseModel):
    profile: Optional[str] = Field(
        default="general",
        description="Execution profile: 'general' (everyday writing), 'technical' (docs/SOPs), or 'aerospace_ste' (strict ASD-STE100 Issue 8).",
    )
    target_identifier: Optional[str] = Field(
        default="task_alpha_01",
        description="Arbitrary tracking or document identifier.",
    )
    query_parameter: Optional[str] = Field(
        default="procedural_text",
        description="Field tag indicating the context of the input text.",
    )
    text_payload: Optional[str] = Field(
        default="Make sure that the valve is closed.",
        description="The source text to analyze and evaluate.",
    )
    lat: Optional[float] = Field(
        default=2.27,
        description="Target latitude clamped to [-90.0, 90.0].",
    )
    lon: Optional[float] = Field(
        default=102.55,
        description="Target longitude clamped to [-180.0, 180.0].",
    )
    window_steps: Optional[int] = Field(
        default=10,
        description="Telemetry observation window steps [1, 100].",
    )


class SpatialRequest(BaseModel):
    lat: Optional[float] = Field(
        default=2.0442,
        description="Latitude for H3 spatial indexing.",
    )
    lon: Optional[float] = Field(
        default=102.5689,
        description="Longitude for H3 spatial indexing.",
    )
    resolution: Optional[int] = Field(
        default=8,
        description="Uber H3 spatial resolution index (0 to 15).",
    )


@app.get("/")
def get_root() -> Dict[str, Any]:
    """Root metadata discovery endpoint."""
    return {
        "service": "AeroSTE-Core",
        "status": "healthy",
        "version": "1.1.0",
        "specification": "Multi-Tier Clarity & ASD-STE100 Issue 8",
        "profiles": ["general", "technical", "aerospace_ste"],
        "endpoints": [
            "/health",
            "/tools",
            "/evaluate_ste_compliance",
            "/get_spatial_h3_tensor",
        ],
    }


@app.get("/health")
def get_health() -> Dict[str, Any]:
    """Liveliness and operational readiness probe."""
    return {"status": "healthy", "service": "AeroSTE-Core"}


@app.get("/tools")
def get_tools_catalog() -> Dict[str, Any]:
    """Catalog of tool schemas for autonomous agent integration."""
    return {
        "status": "healthy",
        "tools": [
            {
                "name": "evaluate_ste_compliance",
                "description": (
                    "Analyzes and scores text clarity deterministically across three tiers: "
                    "'general' (everyday writing), 'technical' (engineering SOPs), and "
                    "'aerospace_ste' (strict ASD-STE100 Issue 8 compliance)."
                ),
                "path": "/evaluate_ste_compliance",
                "method": "POST",
                "parameters": {
                    "profile": "string ('general' | 'technical' | 'aerospace_ste')",
                    "text_payload": "string",
                    "lat": "float",
                    "lon": "float",
                    "window_steps": "integer",
                },
            },
            {
                "name": "get_spatial_h3_tensor",
                "description": "Aggregates regional telemetry into an Uber H3 cell index with facility density calculation.",
                "path": "/get_spatial_h3_tensor",
                "method": "POST",
                "parameters": {
                    "lat": "float",
                    "lon": "float",
                    "resolution": "integer (0-15)",
                },
            },
        ],
    }


@app.api_route("/evaluate_ste_compliance", methods=["GET", "POST"])
def route_evaluate_ste_compliance(
    payload: Optional[ComplianceRequest] = Body(default=None),
) -> Dict[str, Any]:
    """Calculate deterministic clarity, syntax, and controlled language compliance scores."""
    data = payload.model_dump() if payload else {}
    return evaluate_ste_metrics(data)


@app.api_route("/get_spatial_h3_tensor", methods=["GET", "POST"])
def route_get_spatial_h3_tensor(
    payload: Optional[SpatialRequest] = Body(default=None),
) -> Dict[str, Any]:
    """Compute spatial H3 cell index and localized MRO facility density."""
    data = payload.model_dump() if payload else {}
    return compute_h3_spatial_tensor(
        lat=data.get("lat", 2.0442),
        lon=data.get("lon", 102.5689),
        resolution=data.get("resolution", 8),
    )
