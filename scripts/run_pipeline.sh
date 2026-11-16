#!/usr/bin/env bash

# ==============================================================================
# Script Name : run_pipeline.sh
# Description : End-to-End Orchestration Wrapper for Pragati Data Platform
# Usage       : ./scripts/run_pipeline.sh [local|s3]
# ==============================================================================

set -euo pipefail

# Resolve absolute project root directory regardless of where script is invoked
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"

MODE="${1:-local}" # Defaults to 'local' execution; pass 's3' to run cloud pipeline
DATA_FILE="${PROJECT_ROOT}/data/daily_transit_feed.csv"
LOG_DIR="${PROJECT_ROOT}/logs"
LOG_FILE="${LOG_DIR}/pipeline_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "${LOG_DIR}" "${PROJECT_ROOT}/data"

log() {
    echo -e "[$(date +'%Y-%m-%d %H:%M:%S')] [$1] $2" | tee -a "${LOG_FILE}"
}

# Activate virtual environment automatically if available
if [ -f "${PROJECT_ROOT}/venv/bin/activate" ]; then
    source "${PROJECT_ROOT}/venv/bin/activate"
fi

echo "=========================================================================="
log "INFO" "Initializing Pragati Enterprises Data Platform (Mode: ${MODE^^})"
echo "=========================================================================="

# --- STAGE 1: Synthetic Workload Generation ---
log "STAGE-1" "Generating 105,000 production transit logs..."
START_GEN=$(date +%s)

if [ "${MODE}" == "s3" ]; then
    python3 "${PROJECT_ROOT}/src/generate_mock_data.py" --rows 105000 --out "${DATA_FILE}" --upload-s3 >> "${LOG_FILE}" 2>&1
else
    python3 "${PROJECT_ROOT}/src/generate_mock_data.py" --rows 105000 --out "${DATA_FILE}" >> "${LOG_FILE}" 2>&1
fi

END_GEN=$(date +%s)
log "SUCCESS" "Stage 1 completed in $((END_GEN - START_GEN)) seconds."

# --- STAGE 2: ETL Synchronization & MySQL Upsert ---
log "STAGE-2" "Executing ETL ingestion and idempotent MySQL load..."
START_ETL=$(date +%s)

if [ "${MODE}" == "s3" ]; then
    python3 "${PROJECT_ROOT}/src/pipeline_etl.py" --source s3 --archive-s3 >> "${LOG_FILE}" 2>&1
else
    python3 "${PROJECT_ROOT}/src/pipeline_etl.py" --source local --file "${DATA_FILE}" >> "${LOG_FILE}" 2>&1
fi

END_ETL=$(date +%s)
log "SUCCESS" "Stage 2 completed in $((END_ETL - START_ETL)) seconds."

echo "=========================================================================="
log "COMPLETE" "Pipeline run finished. Total Runtime: $((END_ETL - START_GEN))s"
log "AUDIT" "Full execution trace saved to: ${LOG_FILE}"
echo "=========================================================================="
