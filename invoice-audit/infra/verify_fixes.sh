#!/usr/bin/env bash
# 验证两处修复：①原图接口返回 JSON URL（携带 JWT 才能取到，且 Host 自适应）②看板表数据浏览
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login -H 'Content-Type: application/json' \
  -d '{"emp_no":"admin","password":"admin"}' | /conda/miniconda3/envs/SF157/bin/python -c 'import sys,json;print(json.load(sys.stdin)["token"])')
CID=$(curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/dashboard/claims?page_size=1" \
  | /conda/miniconda3/envs/SF157/bin/python -c 'import sys,json;print(json.load(sys.stdin)["items"][0]["id"])')

echo "== 无 token 访问原图（应 401）=="
curl -s -o /dev/null -w 'no-token http=%{http_code}\n' "http://127.0.0.1:8000/api/claims/$CID/file"

echo "== 有 token 访问原图（应 200 + url）=="
URL=$(curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/claims/$CID/file" \
  | /conda/miniconda3/envs/SF157/bin/python -c 'import sys,json;print(json.load(sys.stdin)["url"])')
echo "url=$URL"
echo "Host 自适应检查: $(echo $URL | grep -q '127.0.0.1:9000' && echo 'localhost→127.0.0.1:9000 ✓' || echo 'MISMATCH')"
curl -s -o /dev/null -w '原图下载 http=%{http_code} %{size_download}bytes\n' "$URL"

echo "== 看板表数据浏览（users 密码表）=="
curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/dashboard/table/users?page_size=3" \
  | /conda/miniconda3/envs/SF157/bin/python -c 'import sys,json; d=json.load(sys.stdin); print("columns:", d["columns"]); print("total:", d["total"]); [print(r["emp_no"], r["role"], r["password_hash"][:24]+"...") for r in d["rows"]]'

echo "== 非法表名（应 404）=="
curl -s -o /dev/null -w 'bad-table http=%{http_code}\n' -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/dashboard/table/evil;drop"
