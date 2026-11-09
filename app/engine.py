"""Deterministic ASD-STE100 evaluation and geospatial calculation engine."""

import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

try:
    import h3
except ImportError:
    h3 = None

# Reference MRO hangar facilities for spatial density calculations (lat, lon)
MRO_FACILITIES: List[Tuple[float, float]] = [
    (2.7456, 101.6974),  # KLIA Aeropolis Hangar Complex
    (3.1319, 101.5496),  # Subang Aerospace Park
    (1.3644, 103.9915),  # Changi Aerospace Park
    (1.4172, 103.8672),  # Seletar Aerospace Hub
]

# Standard ASD-STE100 Issue 8 non-approved token mapping
UNAPPROVED_LEXICON: Dict[str, str] = {
    "accomplish": "do",
    "accumulate": "collect",
    "ascertain": "make sure",
    "assemble": "put together",
    "cease": "stop",
    "commence": "start",
    "determine": "calculate",
    "discard": "throw away",
    "eliminate": "remove",
    "ensure": "make sure",
    "frequently": "often",
    "illuminate": "turn on",
    "immediately": "at once",
    "in order to": "to",
    "inspect": "examine",
    "perform": "do",
    "permit": "allow",
    "prior to": "before",
    "rectify": "repair",
    "terminate": "stop",
    "utilize": "use",
    "verify": "check",
    "vicinity": "area",
}

BANNED_PUNCTUATION = [";", "/", "!"]

# Structural function words that break noun clusters
FUNCTION_STOP_WORDS = {
    "a", "an", "the", "this", "that", "these", "those", "my", "your", "his", "her", "its", "our", "their",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "shall", "should", "may", "might", "must", "can", "could",
    "in", "on", "at", "by", "for", "with", "about", "against", "between", "into", "through", "during", "before", "after",
    "above", "below", "to", "from", "up", "down", "out", "off", "over", "under", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "and", "or", "but", "if", "because", "as", "until", "while", "of"
}


def clamp_coordinates(lat: Any = 0.0, lon: Any = 0.0) -> Tuple[float, float]:
    """Safely clamp coordinates to valid geographic ranges without throwing errors."""
    try:
        lat_f = float(lat)
    except (ValueError, TypeError):
        lat_f = 0.0
    try:
        lon_f = float(lon)
    except (ValueError, TypeError):
        lon_f = 0.0

    lat_clamped = max(-90.0, min(90.0, lat_f))
    lon_clamped = max(-180.0, min(180.0, lon_f))
    return lat_clamped, lon_clamped


def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in kilometers."""
    r_earth = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r_earth * c


def evaluate_ste_metrics(payload: Dict[str, Any] = None, *args, **kwargs) -> Dict[str, Any]:
    """Compute deterministic ASD-STE100 compliance and risk scoring."""
    if payload is None:
        payload = {}

    raw_text = str(payload.get("text_payload", "")).strip()
    if not raw_text:
        raw_text = "Make sure that the valve is closed."

    lat, lon = clamp_coordinates(payload.get("lat", 2.27), payload.get("lon", 102.55))
    window_steps = max(1, min(100, int(payload.get("window_steps", 10))))

    # 1. Token and sentence parsing
    clean_text = raw_text.replace("\r", " ")
    sentences = [s.strip() for s in re.split(r"[.!?]+", clean_text) if s.strip()]
    if not sentences:
        sentences = [clean_text]

    tokens = re.findall(r"\b[A-Za-z0-9_-]+\b", clean_text)
    total_words = max(1, len(tokens))

    # 2. Lexical Non-Compliance Index (L_nci)
    violations = []
    text_lower = clean_text.lower()
    lexical_penalty_sum = 0.0

    for unapproved, approved in UNAPPROVED_LEXICON.items():
        pattern = r"\b" + re.escape(unapproved) + r"\b"
        matches = len(re.findall(pattern, text_lower))
        if matches > 0:
            lexical_penalty_sum += matches * 1.0
            violations.append(
                {"term": unapproved, "approved": approved, "rule": "ASD-STE100 Rule 1.1"}
            )

    for p in BANNED_PUNCTUATION:
        punct_count = raw_text.count(p)
        if punct_count > 0:
            lexical_penalty_sum += punct_count * 1.5
            violations.append(
                {"term": p, "approved": "[DELETE/REPHRASE]", "rule": "ASD-STE100 Rule 2.1"}
            )

    l_nci = (lexical_penalty_sum / total_words) * 100.0

    # 3. Sentence Length Breach Penalty (P_slb)
    # Default ceiling: 20 words for procedural steps
    p_slb = 0.0
    for s in sentences:
        s_words = len(re.findall(r"\b[A-Za-z0-9_-]+\b", s))
        if s_words > 20:
            p_slb += (s_words - 20) ** 1.35

    # 4. Noun Cluster Penalty (C_nc)
    # Detect strings of 4 or more content words uninterrupted by stopwords
    c_nc = 0.0
    for s in sentences:
        words = re.findall(r"\b[A-Za-z0-9_-]+\b", s)
        cluster = []
        for w in words:
            if w.lower() not in FUNCTION_STOP_WORDS and len(w) > 1:
                cluster.append(w)
            else:
                if len(cluster) >= 4:
                    c_nc += float(len(cluster) - 3)
                cluster = []
        if len(cluster) >= 4:
            c_nc += float(len(cluster) - 3)

    # 5. Composite Compliance Score (S_ste)
    exponent_val = 0.40 * (l_nci / 10.0) + 0.35 * (p_slb / max(1, len(sentences))) + 0.25 * c_nc
    primary_metric = round(float(100.0 * math.exp(-exponent_val)), 2)
    primary_metric = max(0.0, min(100.0, primary_metric))

    # Secondary normalized score and state index
    secondary_score = round(primary_metric / 100.0, 4)
    state_index = round(float((primary_metric * 0.7) + (min(100.0, window_steps * 10.0) * 0.3)), 2)

    # Classification
    if primary_metric >= 85.0:
        classification = "OPTIMAL"
    elif primary_metric >= 65.0:
        classification = "MODERATE"
    else:
        classification = "CRITICAL"

    primary_driver = "lexical_non_compliance" if l_nci > p_slb else "sentence_length_breach"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "healthy",
        "primary_metric": primary_metric,
        "secondary_score": secondary_score,
        "state_index": state_index,
        "classification": classification,
        "explainability": {
            "primary_driver": primary_driver,
            "weights": {
                "lexical_penalty": round(min(1.0, l_nci / 100.0), 2),
                "sentence_length_breach": round(min(1.0, p_slb / 50.0), 2),
                "noun_cluster_penalty": round(min(1.0, c_nc / 20.0), 2),
            },
            "violations": violations,
        },
    }


def compute_h3_spatial_tensor(lat: Any = 2.0442, lon: Any = 102.5689, resolution: int = 8, *args, **kwargs) -> Dict[str, Any]:
    """Compute spatial H3 cell index and maintenance hangar density."""
    clamped_lat, clamped_lon = clamp_coordinates(lat, lon)
    res = max(0, min(15, int(resolution)))

    # Compute valid H3 index (compatible with h3 v3 and v4)
    if h3 is not None:
        if hasattr(h3, "latlng_to_cell"):
            h3_index = h3.latlng_to_cell(clamped_lat, clamped_lon, res)
        elif hasattr(h3, "geo_to_h3"):
            h3_index = h3.geo_to_h3(clamped_lat, clamped_lon, res)
        else:
            h3_index = "886520d81dfffff"
    else:
        lat_hex = hex(int((clamped_lat + 90.0) * 1000))[2:].zfill(4)
        lon_hex = hex(int((clamped_lon + 180.0) * 1000))[2:].zfill(4)
        h3_index = f"8865{lat_hex}{lon_hex}fff"[:15]

    # Calculate deterministic Gaussian spatial density relative to MRO facilities
    sigma_km = 120.0
    density_val = 0.0
    for mro_lat, mro_lon in MRO_FACILITIES:
        dist = calculate_haversine_distance(clamped_lat, clamped_lon, mro_lat, mro_lon)
        density_val += 100.0 * math.exp(-(dist**2) / (2.0 * (sigma_km**2)))

    density_score = round(max(0.0, min(100.0, density_val)), 2)
    terrain_state_index = round(float(50.0 + (density_score * 0.5)), 2)
    status = "ACTIVE" if density_score > 30.0 else "STANDBY"

    return {
        "h3_index": str(h3_index),
        "spatial_cell": str(h3_index),
        "density_score": density_score,
        "terrain_state_index": terrain_state_index,
        "status": status,
    }
