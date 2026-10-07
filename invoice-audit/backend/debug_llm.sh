#!/usr/bin/env bash
# 直接 curl DeepSeek 看错误详情
set -a
source $SCRIPT_DIR/../.env
set +a
echo "--- 基础调用 ---"
curl -sS -X POST "$DEEPSEEK_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$DEEPSEEK_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"回复OK两个字\"}],\"stream\":false}" | head -c 1200
echo ""
echo "--- 带 tools 调用 ---"
curl -sS -X POST "$DEEPSEEK_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-flash","messages":[{"role":"user","content":"调用 get_info 工具"}],"tools":[{"type":"function","function":{"name":"get_info","description":"获取信息","parameters":{"type":"object","properties":{}}}}],"tool_choice":{"type":"function","function":{"name":"get_info"}},"stream":false}' | head -c 1500
