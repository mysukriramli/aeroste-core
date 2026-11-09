# AeroSTE-Core

[![Test Suite](https://github.com/mysukriramli/aeroste-core/actions/workflows/test.yml/badge.svg)](https://github.com/mysukriramli/aeroste-core/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-brightgreen.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Standard: ASD--STE100](https://img.shields.io/badge/Standard-ASD--STE100_Issue_8-orange.svg)](rules/rules.md)

Deterministic multi-tier text clarity, technical SOP linting, and ASD-STE100 Issue 8 compliance engine with geospatial maintenance telemetry for autonomous agents.

---

## Architecture Overview

AeroSTE-Core acts as a deterministic compiler for human and AI-generated communication. Instead of relying on stochastic LLM judging, it evaluates text using closed-form mathematical penalties, strict token dictionaries, and geospatial distance decay fields.

```text
aeroste-core/
├── .github/workflows/
│   ├── test.yml                 # Automated pytest CI pipeline
│   └── process_input.yml        # Event-driven input/ -> output/ batch queue
├── app/
│   ├── __init__.py
│   ├── engine.py                # Mathematical scoring, lexicon matrix, H3 spatial tensor
│   └── main.py                  # FastAPI operational service with OpenAPI tool catalog
├── input/                       # Drop directory for raw drafts (.txt, .md)
├── output/                      # Normalized compliant output directory (*.ste.md)
├── rules/
│   ├── rules.md                 # Syntactic rules, sentence limits, punctuation bans
│   └── vocabulary.md            # ASD-STE100 Issue 8 controlled substitution matrix
├── scripts/
│   └── process_queue.py         # Autonomous batch transformation runner
├── tests/
│   ├── __init__.py
│   └── test_api.py              # 5-stage deterministic test suite
├── llms.txt                     # Compact root manifest for LLM discovery (<800 tokens)
├── mcp_server.py                # FastMCP server for Claude Desktop, Cursor, and Cline
└── requirements.txt
