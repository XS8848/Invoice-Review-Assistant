#!/usr/bin/env bash
# 一键运行全部测试：单元 → API → 压力(locust) → 管道吞吐
export PATH=/conda/miniconda3/envs/SF157/bin:$PATH
PY=/conda/miniconda3/envs/SF157/bin/python
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==================== [1/4] 单元测试 ===================="
$PY -m pytest unit -q --tb=short -p no:cacheprovider

echo "==================== [2/4] API 功能/业务流转/安全 ===================="
$PY -m pytest api/test_auth.py api/test_business_flow.py api/test_edge_security.py api/test_admin_api.py -q --tb=short -p no:cacheprovider

echo "==================== [3/4] 压力测试 (locust 90s) ===================="
$PY -m locust -f load/locustfile.py --headless -u 40 -r 8 -t 90s \
  --host http://127.0.0.1:8000 --csv=/tmp/locust --only-summary 2>&1 | tail -35

echo "==================== [4/4] 管道吞吐测试 (20文件批次) ===================="
$PY load/pipeline_throughput.py
