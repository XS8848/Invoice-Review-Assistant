#!/usr/bin/env bash
export PATH=/conda/miniconda3/envs/SF157/bin:$PATH
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
/conda/miniconda3/envs/SF157/bin/python -m locust -f load/locustfile.py --headless -u 40 -r 8 -t 90s \
  --host http://127.0.0.1:8000 --csv=/tmp/locust --only-summary 2>&1 | tail -40
echo "--- stats csv ---"
head -12 /tmp/locust_stats.csv
