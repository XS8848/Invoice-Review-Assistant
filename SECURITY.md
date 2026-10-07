# 安全策略

## 🔒 凭据管理

本仓库**不包含任何真实凭据**。所有敏感信息通过环境变量注入。

### 被 `.gitignore` 强制排除的文件

| 文件 | 内容 | 处理方式 |
|---|---|---|
| `invoice-audit/.env` | DeepSeek API Key、MySQL 密码、JWT 密钥、MinIO 密钥 | 绝不入库 |
| `deploy.local.env` | 本地部署覆盖配置 | 绝不入库 |
| `*.db` / `*.sqlite` | 本地数据库 | 绝不入库 |
| `uploads/` | 用户上传的发票原件（含个人隐私信息） | 绝不入库 |
| `minio-data/` | 对象存储数据 | 绝不入库 |
| `*.pem` / `*.key` | 证书与私钥 | 绝不入库 |

### 首次部署

```bash
cp invoice-audit/.env.example invoice-audit/.env
# 然后填入你自己的真实凭据
```

`.env.example` 中所有值均为占位符（`sk-xxxx`、`change-me`），可直接安全入库。

---

## 🔑 如果密钥意外泄露

本仓库为**公开仓库**。若你曾经将 `.env` 或其他含凭据的文件提交并推送到公开位置，请立即执行：

1. **重置 DeepSeek API Key** — <https://platform.deepseek.com/api_keys>
2. **重置 MySQL `invoice` 账号密码** — `ALTER USER 'invoice'@'localhost' IDENTIFIED BY '<新密码>';`
3. **重置 MinIO `SECRET_KEY`**
4. **重新生成 `JWT_SECRET`** — `python -c "import secrets; print(secrets.token_hex(32))"`
5. 用 [BFG Repo-Cleaner](https://github.com/newrid/bfg) 或 `git filter-repo` 清理历史记录

> 单纯删除文件**不足以**清除历史 —— 已推送的密钥永久留在 git 对象库中，必须重置凭据 + 清理历史双管齐下。

---

## 🛡️ 上传文件隐私

发票属于个人敏感信息。本项目的 `.gitignore` 已排除：

- `*.pdf` / `*.jpg` / `*.jpeg` / `*.png` / `*.ofd` — 发票原件
- `uploads/` — 运行时上传目录
- `tests/ui/screenshots/` — 测试过程截图

**部署到公网前请确认：** 对象存储桶（`reimb-invoices`）未开启公开读策略，且已配置生命周期清理策略。

---

## 🐛 漏洞报告

发现安全问题请**不要**公开提交 Issue。
请通过 GitHub 仓库的 Security Advisory 私密上报，或直接联系维护者。
