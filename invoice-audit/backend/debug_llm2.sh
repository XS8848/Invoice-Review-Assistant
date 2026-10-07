#!/usr/bin/env bash
set -a
source $SCRIPT_DIR/../.env
set +a
echo "--- 非思考模式 + 强制 tool_choice ---"
curl -sS -X POST "$DEEPSEEK_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-flash","thinking":{"type":"disabled"},"temperature":0.1,"messages":[{"role":"user","content":"调用 get_info 工具"}],"tools":[{"type":"function","function":{"name":"get_info","description":"获取信息","parameters":{"type":"object","properties":{}}}}],"tool_choice":{"type":"function","function":{"name":"get_info"}},"stream":false}' | head -c 800
echo ""
