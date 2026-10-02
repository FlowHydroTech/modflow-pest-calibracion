#!/bin/bash
set -e
echo "entrypoint dummy autonomo - $(date '+%Y-%m-%d %H:%M:%S')"
echo "CALIBRATION_ID=${CALIBRATION_ID:-none} BUCKET_NAME=${BUCKET_NAME:-none}"
/app/pest_hp
echo "entrypoint dummy finished"