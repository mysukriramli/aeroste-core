"""Autonomous 24/7 background worker client for AeroSTE-Core.

Monitors input/ for new or modified files, executes the multi-tier compliance
pipeline, tracks processed state to prevent redundant cycles, and writes
normalized documents into output/.
"""

import hashlib
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from scripts.process_queue import process_file

# Configuration defaults
REPO_ROOT = Path(__file__).resolve().parent
INPUT_DIR = REPO_ROOT / "input"
OUTPUT_DIR = REPO_ROOT / "output"
STATE_FILE = REPO_ROOT / ".agent_state.json"
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))

# Structured logger setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("AeroSTE-Agent")

# Graceful termination handler
RUNNING = True


def handle_shutdown(signum, frame):
    """Handle SIGINT and SIGTERM for clean shutdown."""
    global RUNNING
    logger.info(f"Shutdown signal ({signum}) received. Finishing current cycle...")
    RUNNING = False


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


def calculate_file_hash(path: Path) -> str:
    """Compute SHA-256 digest of file content to detect new/modified files."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_manifest() -> dict:
    """Load previously processed file hashes from disk."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Could not read state file, resetting: {e}")
    return {}


def save_manifest(manifest: dict):
    """Persist processed file hashes to disk."""
    STATE_FILE.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def poll_and_process(manifest: dict) -> int:
    """Inspect input/ directory and process unhandled or modified documents."""
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    candidates = [
        f for f in INPUT_DIR.iterdir()
        if f.is_file() and not f.name.startswith(".") and f.suffix.lower() in [".md", ".txt"]
    ]

    processed_count = 0

    for file_path in candidates:
        try:
            current_hash = calculate_file_hash(file_path)
        except Exception as e:
            logger.error(f"Cannot read {file_path.name}: {e}")
            continue

        last_known_hash = manifest.get(file_path.name)

        # Process only if the file is new or its content has changed
        if current_hash != last_known_hash:
            logger.info(f"Processing candidate document: {file_path.name}")
            try:
                process_file(file_path)
                manifest[file_path.name] = current_hash
                save_manifest(manifest)
                processed_count += 1
            except Exception as e:
                logger.error(f"Error processing {file_path.name}: {e}")

    return processed_count


def run_worker():
    """Main 24/7 event loop."""
    logger.info("=" * 70)
    logger.info(" AeroSTE-Core: Autonomous 24/7 File Ingestion Worker")
    logger.info(f" Monitored Path : {INPUT_DIR}")
    logger.info(f" Output Target  : {OUTPUT_DIR}")
    logger.info(f" Polling Window : Every {POLL_INTERVAL} seconds")
    logger.info("=" * 70)

    manifest = load_manifest()

    while RUNNING:
        try:
            items_handled = poll_and_process(manifest)
            if items_handled > 0:
                logger.info(f"Cycle complete. {items_handled} document(s) transformed.")
        except Exception as e:
            logger.error(f"Unexpected cycle failure: {e}")

        # Sleep interval with periodic checks to allow instant exit on shutdown
        for _ in range(POLL_INTERVAL):
            if not RUNNING:
                break
            time.sleep(1)

    logger.info("Worker process exited gracefully.")


if __name__ == "__main__":
    run_worker()
