"""FastAPI operational service for ASD-STE100 compliance and aerospace telemetry."""

from typing import Any, Dict, Optional
from fastapi import FastAPI, Body
from pydantic import BaseModel, Field

from app.engine import evaluate_ste_metrics, compute_h3_spatial_tensor

app = FastAPI(
    title="AeroSTE-Core",
    version="1.0.0",
    description="Deterministic ASD-STE100 Compliance & Aerospace Field Telemetry Engine",
)


class ComplianceRequest(BaseModel):
    target_identifier: Optional[str] = Field(default="task_alpha_01")
    query_parameter: Optional[str] = Field(default="procedural_text")
    text_payload: Optional[str] = Field(
        default="Make sure that the valve is closed."
    )
    lat: Optional[float] = Field(default=2.27)
    lon: Optional[float] = Field(default=102.55)
    window_steps: Optional[int] = Field(default=10)


class SpatialRequest(BaseModel):
    lat: Optional[float] = Field(default=2.0442)
    lon: Optional[float] = Field(default=102.5689)
    resolution: Optional[int] = Field(default=8)


@app.get("/")
def get_root() -> Dict[str, Any]:
    """Root metadata discovery endpoint."""
    return {
        "service": "AeroSTE-Core",
        "status": "healthy",
        "specification": "ASD-STE100 Issue 8",
        "endpoints": ["/health", "/tools", "/evaluate_ste_compliance", "/get_spatial_h3_tensor"],
    }


@app.get("/health")
def get_health() -> Dict[str, Any]:
    """Liveliness probe."""
    return {"status": "healthy", "service": "AeroSTE-Core"}


@app.get("/tools")
def get_tools_catalog() -> Dict[str, Any]:
    """Catalog of tool schemas for agentic integration."""
    return {
        "status": "healthy",
        "tools": [
            {
                "name": "evaluate_ste_compliance",
                "description": "Evaluates raw text against ASD-STE100 Issue 8 bounds.",
                "path": "/evaluate_ste_compliance",
                "method": "POST",
            },
            {
                "name": "get_spatial_h3_tensor",
                "description": "Aggregates regional metrics into an Uber H3 cell index.",
                "path": "/get_spatial_h3_tensor",
                "method": "POST",
            },
        ],
    }


@app.api_route("/evaluate_ste_compliance", methods=["GET", "POST"])
def route_evaluate_ste_compliance(
    payload: Optional[ComplianceRequest] = Body(default=None),
) -> Dict[str, Any]:
    """Calculate deterministic STE compliance scores."""
    data = payload.model_dump() if payload else {}
    return evaluate_ste_metrics(data)


@app.api_route("/get_spatial_h3_tensor", methods=["GET", "POST"])
def route_get_spatial_h3_tensor(
    payload: Optional[SpatialRequest] = Body(default=None),
) -> Dict[str, Any]:
    """Compute spatial H3 density and cell resolution."""
    data = payload.model_dump() if payload else {}
    return compute_h3_spatial_tensor(
        lat=data.get("lat", 2.0442),
        lon=data.get("lon", 102.5689),
        resolution=data.get("resolution", 8),
    )
