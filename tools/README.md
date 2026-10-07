# 凭据生成工具

`tools/gen_secrets.py` —— 为本项目生成密码学安全的凭据。

## 用法

```bash
# 仅打印，不改任何文件（推荐先看效果）
python tools/gen_secrets.py

# 生成后直接追加写入 invoice-audit/.env
python tools/gen_secrets.py --env
```

## 生成的四类凭据

| 键 | 生成方式 | 形态 | 约束来源 |
|---|---|---|---|
| `JWT_SECRET` | `secrets.token_hex(32)` | 64 位十六进制 | 本项目签名密钥 |
| `MINIO_ACCESS_KEY` | 自定义字典 | `invoice` + 6 位小写字母数字 | 需短、无特殊符号 |
| `MINIO_SECRET_KEY` | Base64 风格字典 | 40 字符 | MinIO 要求 8~40 |
| `DATABASE_URL` | 内嵌随机密码 | `mysql+pymysql://...` | 必须 URL 安全 |

> `DEEPSEEK_API_KEY` **无法本地生成**，只能在 <https://platform.deepseek.com/api_keys> 申请。

## 三条设计原则

**1. 只用 `secrets`，不用 `random`**

`random` 是梅森旋转伪随机，输出可由前几个值反推；`secrets` 底层是 `os.urandom`，是操作系统级的真随机源，属于密码学安全范畴。

**2. 剔除易混淆字符**

密码字符集里去掉了 `I O l 0 1`。
人工抄写密码时，`0` 常被误认成 `O`、`1` 被误认成 `l`/`I`，这是登不进数据库的常见原因。

**3. 特殊符号只用 URL 安全字符**

MySQL 密码必须包含特殊符号（8.0 默认密码策略要求四类齐全），但符号一旦放进
`DATABASE_URL` 就会出问题。脚本只使用 RFC 3986 安全的 `!*-._~`：

| 被排除的符号 | 排除原因 |
|---|---|
| `$` `` ` `` `\` | shell 变量展开、`\` 转义 |
| `'` `"` | 引号截断，YAML 也不友好 |
| `;` `&` | 命令分隔符 |
| `=` `?` `#` | 破坏 URL 的 `k=v` 与查询串结构 |
| `%` | 在 URL 中必须写成 `%25` |
| `/` `@` `:` | URL 结构分隔符 |

改库时，脚本会同时输出 `localhost` 和 `127.0.0.1` 两条 `ALTER USER` 语句 —— MySQL 的账号是按 Host 分别授权的，只改一处会出现「本地能连、连不上 127.0.0.1」的问题。

## 换密钥的正确顺序

1. `python tools/gen_secrets.py` 生成新值
2. 写进 `invoice-audit/.env`
3. **JWT_SECRET**：所有已签发 token 立即失效，用户需重新登录
4. **MINIO_SECRET_KEY**：需同步改 `start_minio.sh`，否则后端连不上对象存储
5. **DATABASE_URL**：先执行输出的两条 `ALTER USER` 改库，再改 `.env`，顺序反了会连不上

## ⚠️ 注意事项

- 生成的凭据**只在终端显示一次**，关闭后无法再查看，请立即保存
- **不要**把生成的凭据粘贴到聊天窗口、Issue 或 PR 里
- `invoice-audit/.env` 已被 `.gitignore` 排除，不会误入库
- 泄露后的应急流程见 [SECURITY.md](../SECURITY.md)
