#!/usr/bin/env bash
set -uo pipefail

MODEL_TIMEOUT="${MODEL_TIMEOUT:-15h}"

timeout --kill-after=60s "$MODEL_TIMEOUT" bash ./ensibatch.sh
status=$?

if [ "$status" -eq 124 ] || [ "$status" -eq 137 ]; then
  echo "MODEL TIMEOUT: ensbatch.sh excedio $MODEL_TIMEOUT" >&2
fi

exit "$status"
