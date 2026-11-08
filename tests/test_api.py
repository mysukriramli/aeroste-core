"""Automated deterministic test suite for AeroSTE-Core."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.engine import evaluate_ste_metrics, compute_h3_spatial_tensor

client = TestClient(app)


def test_1_liveliness_and_tool_discovery():
    """Verify liveliness probes and tool catalog schemas."""
    # Check root metadata
    resp_root = client.get("/")
    assert resp_root.status_code == 200
    root_data = resp_root.json()
    assert root_data["status"] == "healthy"
    assert "specification" in root_data

    # Check health probe
    resp_health = client.get("/health")
    assert resp_health.status_code == 200
    assert resp_health.json()["status"] == "healthy"

    # Check tool catalog
    resp_tools = client.get("/tools")
    assert resp_tools.status_code == 200
    tools_data = resp_tools.json()
    assert tools_data["status"] == "healthy"
    tool_names = [t["name"] for t in tools_data.get("tools", [])]
    assert "evaluate_ste_compliance" in tool_names
    assert "get_spatial_h3_tensor" in tool_names


def test_2_zero_parameter_route_resilience():
    """Verify all routes return HTTP 200 when invoked without query or body parameters."""
    # Test GET without parameters
    resp_ste_get = client.get("/evaluate_ste_compliance")
    assert resp_ste_get.status_code == 200
    assert resp_ste_get.json()["status"] == "healthy"

    resp_spatial_get = client.get("/get_spatial_h3_tensor")
    assert resp_spatial_get.status_code == 200
    assert "h3_index" in resp_spatial_get.json()

    # Test POST with empty payload
    resp_ste_post = client.post("/evaluate_ste_compliance", json={})
    assert resp_ste_post.status_code == 200
    assert resp_ste_post.json()["primary_metric"] >= 0.0

    resp_spatial_post = client.post("/get_spatial_h3_tensor", json={})
    assert resp_spatial_post.status_code == 200
    assert len(resp_spatial_post.json()["h3_index"]) == 15


def test_3_mathematical_monotonicity_and_sensitivity():
    """Verify compliant text scores higher than run-on text with unapproved terms."""
    compliant_payload = {
        "text_payload": "Make sure that the valve is closed. Clean the seal surface.",
        "window_steps": 10,
    }
    non_compliant_payload = {
        "text_payload": "Technicians must continuously utilize chemical solvent in order to eliminate grease prior to commencing assembly; verify alignment immediately!",
        "window_steps": 10,
    }

    result_compliant = evaluate_ste_metrics(compliant_payload)
    result_non_compliant = evaluate_ste_metrics(non_compliant_payload)

    # Monotonicity assertion: Clean text must yield a higher compliance score
    assert result_compliant["primary_metric"] > result_non_compliant["primary_metric"]
    assert result_compliant["classification"] in ["OPTIMAL", "MODERATE"]
    assert result_non_compliant["classification"] == "CRITICAL"
    assert len(result_non_compliant["explainability"]["violations"]) >= 3


def test_4_determinism_assertion():
    """Verify identical parameters produce bitwise identical numeric metrics."""
    test_payload = {
        "text_payload": "Examine the rotor blades for cracks. If you find wear marks, discard the seal.",
        "lat": 3.1319,
        "lon": 101.5496,
        "window_steps": 15,
    }

    run_1 = evaluate_ste_metrics(test_payload)
    run_2 = evaluate_ste_metrics(test_payload)

    # Strict equality on numeric outputs
    assert run_1["primary_metric"] == run_2["primary_metric"]
    assert run_1["secondary_score"] == run_2["secondary_score"]
    assert run_1["state_index"] == run_2["state_index"]
    assert run_1["classification"] == run_2["classification"]
    assert (
        run_1["explainability"]["weights"]
        == run_2["explainability"]["weights"]
    )


def test_5_spatial_h3_integrity():
    """Verify spatial tensors resolve valid 15-char H3 hex indexes across extreme coordinates."""
    # Standard coordinate
    tensor_std = compute_h3_spatial_tensor(lat=2.0442, lon=102.5689, resolution=8)
    assert len(tensor_std["h3_index"]) == 15
    assert tensor_std["density_score"] >= 0.0

    # Extreme boundary latitude (North Pole clamping)
    tensor_north = compute_h3_spatial_tensor(lat=89.99, lon=0.0, resolution=8)
    assert len(tensor_north["h3_index"]) == 15

    # Out-of-bounds coordinates clamped safely without error
    tensor_clamped = compute_h3_spatial_tensor(lat=150.0, lon=-250.0, resolution=8)
    assert len(tensor_clamped["h3_index"]) == 15
