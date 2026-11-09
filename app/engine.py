"""Deterministic text clarity, technical documentation, and ASD-STE100 engine with offset tracking, diff patching, and SARIF support."""

import difflib
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    import h3
except ImportError:
    h3 = None

# In-memory execution cache for 24/7 agentic deduplication
EVALUATION_CACHE: Dict[str, Dict[str, Any]] = {}
MAX_CACHE_SIZE = 10000

# Reference MRO facilities for spatial density calculations (lat, lon)
MRO_FACILITIES: List[Tuple[float, float]] = [
    (2.7456, 101.6974),  # KLIA Aeropolis Hangar Complex
    (3.1319, 101.5496),  # Subang Aerospace Park
    (1.3644, 103.9915),  # Changi Aerospace Park
    (1.4172, 103.8672),  # Seletar Aerospace Hub
]

# Tier 1: General English Fluff & Bloat Replacement Dictionary
GENERAL_CLUTTER_LEXICON: Dict[str, str] = {
    "in order to": "to",
    "due to the fact that": "because",
    "at this point in time": "now",
    "utilize": "use",
    "utilization": "use",
    "commence": "start",
    "terminate": "end",
    "facilitate": "help",
    "implement": "carry out / start",
    "subsequent to": "after",
    "prior to": "before",
    "in the event that": "if",
    "with reference to": "about",
    "for the purpose of": "to",
    "in accordance with": "under / by",
}

# Tier 3: Strict ASD-STE100 Issue 8 non-approved token mapping
STE_LEXICON: Dict[str, str] = {
    **GENERAL_CLUTTER_LEXICON,
    "accomplish": "do",
    "accumulate": "collect",
    "ascertain": "make sure",
    "assemble": "put together",
    "cease": "stop",
    "determine": "calculate",
    "discard": "throw away",
    "eliminate": "remove",
    "ensure": "make sure",
    "frequently": "often",
    "illuminate": "turn on",
    "immediately": "at once",
    "inspect": "examine",
    "perform": "do",
    "permit": "allow",
    "rectify": "repair",
    "verify": "check",
    "vicinity": "area",
}

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
    """Safely clamp coordinates to valid geographic ranges without throwing exceptions."""
    try:
        lat_f = float(lat)
    except (ValueError, TypeError):
        lat_f = 0.0
    try:
        lon_f = float(lon)
    except (ValueError, TypeError):
        lon_f = 0.0

    return max(-90.0, min(90.0, lat_f)), max(-180.0, min(180.0, lon_f))


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
    return r_earth * (2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a)))


def compute_line_col(text: str, offset: int) -> Tuple[int, int]:
    """Convert an absolute character index into 1-based (line, column) coordinates."""
    line = text.count("\n", 0, offset) + 1
    last_nl = text.rfind("\n", 0, offset)
    col = offset + 1 if last_nl == -1 else (offset - last_nl)
    return line, col


def generate_patch(original: str, edits: List[Dict[str, Any]]) -> Tuple[str, str]:
    """Apply non-overlapping byte replacements in reverse order and return the transformed text and unified diff."""
    # Sort descending by start index to prevent coordinate drift during substitution
    sorted_edits = sorted(edits, key=lambda e: e["start"], reverse=True)
    transformed = original

    for edit in sorted_edits:
        s, e, rep = edit["start"], edit["end"], edit["replacement"]
        if rep != "[REPHRASE]":
            orig_slice = transformed[s:e]
            if orig_slice.isupper():
                rep_cased = rep.upper()
            elif orig_slice and orig_slice[0].isupper():
                rep_cased = rep.capitalize()
            else:
                rep_cased = rep
            transformed = transformed[:s] + rep_cased + transformed[e:]

    # Post-repair capitalization after period separations
    transformed = re.sub(r'(?<=\.\s)([a-z])', lambda m: m.group(1).upper(), transformed)

    diff_lines = list(difflib.unified_diff(
        original.splitlines(keepends=True),
        transformed.splitlines(keepends=True),
        fromfile="original",
        tofile="compliant",
        n=3
    ))
    patch_str = "".join(diff_lines)
    return transformed, patch_str


def evaluate_ste_metrics(payload: Optional[Dict[str, Any]] = None, *args, **kwargs) -> Dict[str, Any]:
    """Compute deterministic text compliance with character offsets and diff generation."""
    if payload is None:
        payload = {}

    raw_text = str(payload.get("text_payload", "")).strip()
    if not raw_text:
        raw_text = "Make sure that the valve is closed."

    profile = str(payload.get("profile", "aerospace_ste")).lower().strip()
    if profile not in ["general", "technical", "aerospace_ste"]:
        profile = "aerospace_ste"

    lat, lon = clamp_coordinates(payload.get("lat", 2.27), payload.get("lon", 102.55))
    window_steps = max(1, min(100, int(payload.get("window_steps", 10))))

    # SHA-256 cache check
    cache_payload = f"{profile}:{raw_text}:{window_steps}"
    cache_key = hashlib.sha256(cache_payload.encode("utf-8")).hexdigest()

    if cache_key in EVALUATION_CACHE:
        cached_result = EVALUATION_CACHE[cache_key].copy()
        cached_result["timestamp"] = datetime.now(timezone.utc).isoformat()
        return cached_result

    # Profile configurations
    if profile == "general":
        max_sentence_len = 35
        lexicon_target = GENERAL_CLUTTER_LEXICON
        banned_punctuations = []
        cluster_threshold = 5
    elif profile == "technical":
        max_sentence_len = 25
        lexicon_target = GENERAL_CLUTTER_LEXICON
        banned_punctuations = ["/"]
        cluster_threshold = 4
    else:  # aerospace_ste (Strict Issue 8)
        max_sentence_len = 20
        lexicon_target = STE_LEXICON
        banned_punctuations = [";", "/", "!"]
        cluster_threshold = 4

    clean_text = raw_text.replace("\r", " ")
    sentences = [s.strip() for s in re.split(r"[.!?]+", clean_text) if s.strip()]
    if not sentences:
        sentences = [clean_text]

    tokens = re.findall(r"\b[A-Za-z0-9_-]+\b", clean_text)
    total_words = max(1, len(tokens))

    # 1. Lexical checks with character offset tracking
    violations = []
    edits = []
    lexical_penalty = 0.0

    # Sort descending by length to avoid partial-token match collision
    sorted_terms = sorted(lexicon_target.keys(), key=len, reverse=True)
    for term in sorted_terms:
        alternative = lexicon_target[term]
        pattern = r"\b" + re.escape(term) + r"\b"
        for match in re.finditer(pattern, clean_text, re.IGNORECASE):
            s_idx, e_idx = match.start(), match.end()
            line, col = compute_line_col(clean_text, s_idx)
            lexical_penalty += 1.0

            violation_entry = {
                "term": term,
                "approved": alternative,
                "rule": f"{profile.upper()}_LEXICAL",
                "start": s_idx,
                "end": e_idx,
                "line": line,
                "column": col
            }
            violations.append(violation_entry)
            edits.append({
                "start": s_idx,
                "end": e_idx,
                "original": match.group(0),
                "replacement": alternative
            })

    for p in banned_punctuations:
        rep = "." if p in [";", "!"] else " and "
        for idx, ch in enumerate(clean_text):
            if ch == p:
                line, col = compute_line_col(clean_text, idx)
                lexical_penalty += 1.5
                violations.append({
                    "term": p,
                    "approved": "[REPHRASE]",
                    "rule": f"{profile.upper()}_PUNCTUATION",
                    "start": idx,
                    "end": idx + 1,
                    "line": line,
                    "column": col
                })
                edits.append({
                    "start": idx,
                    "end": idx + 1,
                    "original": p,
                    "replacement": rep
                })

    l_nci = (lexical_penalty / total_words) * 100.0

    # 2. Sentence length checks
    p_slb = 0.0
    for s in sentences:
        s_words = len(re.findall(r"\b[A-Za-z0-9_-]+\b", s))
        if s_words > max_sentence_len:
            p_slb += (s_words - max_sentence_len) ** 1.35

    # 3. Dense word clustering
    c_nc = 0.0
    for s in sentences:
        words = re.findall(r"\b[A-Za-z0-9_-]+\b", s)
        cluster = []
        for w in words:
            if w.lower() not in FUNCTION_STOP_WORDS and len(w) > 1:
                cluster.append(w)
            else:
                if len(cluster) >= cluster_threshold:
                    c_nc += float(len(cluster) - (cluster_threshold - 1))
                cluster = []
        if len(cluster) >= cluster_threshold:
            c_nc += float(len(cluster) - (cluster_threshold - 1))

    # 4. Composite Scoring Formula
    exponent_val = 0.40 * (l_nci / 10.0) + 0.35 * (p_slb / max(1, len(sentences))) + 0.25 * c_nc
    primary_metric = round(float(100.0 * math.exp(-exponent_val)), 2)
    primary_metric = max(0.0, min(100.0, primary_metric))

    secondary_score = round(primary_metric / 100.0, 4)
    state_index = round(float((primary_metric * 0.7) + (min(100.0, window_steps * 10.0) * 0.3)), 2)

    if primary_metric >= 85.0:
        classification = "OPTIMAL"
    elif primary_metric >= 65.0:
        classification = "MODERATE"
    else:
        classification = "CRITICAL"

    primary_driver = "lexical_non_compliance" if l_nci > p_slb else "sentence_length_breach"

    # Generate unified diff patch and reconstructed compliant text
    transformed_text, unified_patch = generate_patch(raw_text, edits)

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "healthy",
        "profile": profile,
        "primary_metric": primary_metric,
        "secondary_score": secondary_score,
        "state_index": state_index,
        "classification": classification,
        "patch": unified_patch,
        "transformed_text": transformed_text,
        "explainability": {
            "primary_driver": primary_driver,
            "weights": {
                "lexical_penalty": round(min(1.0, l_nci / 100.0), 2),
                "sentence_length_breach": round(min(1.0, p_slb / 50.0), 2),
                "noun_cluster_penalty": round(min(1.0, c_nc / 20.0), 2),
            },
            "violations": violations,
            "edits": edits,
        },
    }

    if len(EVALUATION_CACHE) >= MAX_CACHE_SIZE:
        EVALUATION_CACHE.pop(next(iter(EVALUATION_CACHE)))
    EVALUATION_CACHE[cache_key] = result

    return result


def generate_sarif_report(evaluation: Dict[str, Any], file_uri: str = "document.md") -> Dict[str, Any]:
    """Export compliance violations into the standard SARIF v2.1.0 JSON format for GitHub Code Scanning."""
    rules_map = {}
    results = []

    for idx, v in enumerate(evaluation.get("explainability", {}).get("violations", [])):
        rule_id = v.get("rule", "STE_COMPLIANCE")
        if rule_id not in rules_map:
            rules_map[rule_id] = {
                "id": rule_id,
                "shortDescription": {"text": f"Controlled Language Rule: {rule_id}"},
                "help": {"text": f"Replace '{v.get('term')}' with approved term '{v.get('approved')}'."}
            }

        results.append({
            "ruleId": rule_id,
            "level": "error" if evaluation.get("classification") == "CRITICAL" else "warning",
            "message": {
                "text": f"Non-compliant token '{v.get('term')}'. Replace with '{v.get('approved')}'."
            },
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": file_uri},
                        "region": {
                            "startLine": v.get("line", 1),
                            "startColumn": v.get("column", 1),
                            "endColumn": v.get("column", 1) + len(v.get("term", ""))
                        }
                    }
                }
            ]
        })

    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "AeroSTE-Core",
                        "version": "1.1.0",
                        "informationUri": "https://github.com/mysukriramli/aeroste-core",
                        "rules": list(rules_map.values())
                    }
                },
                "results": results
            }
        ]
    }


def compute_h3_spatial_tensor(lat: Any = 2.0442, lon: Any = 102.5689, resolution: int = 8, *args, **kwargs) -> Dict[str, Any]:
    """Compute spatial H3 cell index and localized MRO facility density."""
    clamped_lat, clamped_lon = clamp_coordinates(lat, lon)
    res = max(0, min(15, int(resolution)))

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
