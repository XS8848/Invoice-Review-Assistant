#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发票审计系统 · 凭据生成器

用法：
    python tools/gen_secrets.py            # 仅打印，不写文件
    python tools/gen_secrets.py --env      # 直接追加写入 .env（跳过已存在的键）

安全性：
    - 使用 Python 标准库 secrets（基于 os.urandom 的密码学安全随机源），
      不要用 random 模块，random 是伪随机、可预测。
    - 生成的凭据仅在本地终端显示，请勿粘贴到聊天窗口、Issue 或提交入库。
"""

import argparse
import secrets
import string
import sys

# ---------------------------------------------------------------- 生成规则

# MySQL 8 密码策略：默认要求长度 >= 8，且需包含大小写字母、数字、特殊符号。
# 去掉容易混淆的字符 0/O/1/l/I，避免人工抄写时出错。
_MYSQL_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"   # 无 I O
_MYSQL_LOWER = "abcdefghijkmnpqrstuvwxyz"   # 无 l
_MYSQL_DIGIT = "23456789"                  # 无 0 1
# 只用 URL 安全字符（RFC 3986 unreserved + sub-delims 中的 !*-._~）
# 刻意排除 $ ` \ ' " ; & = ? # % ：这些放进 DATABASE_URL 会破坏 URL 解析，
# 且 $ \ ` " ' 在 shell 与 YAML 中还会触发变量展开或引号截断。
# 不用百分号 % 是因为它在 URL 中必须写成 %25。
_MYSQL_SPECIAL = "!*-._~"

# MinIO 要求 SECRET_KEY 长度为 8~40
_MINIO_SPECIAL = "+/"                      # Base64 风格，MinIO 官方文档推荐


def gen_jwt_secret() -> str:
    """JWT 签名密钥：64 位十六进制（256 bit）。

    选 hex 编码的原因：纯 [0-9a-f]，在任何配置文件、YAML、命令行环境变量里
    都不会引发转义或引号问题。
    """
    return secrets.token_hex(32)


def gen_mysql_password(length: int = 20) -> str:
    """MySQL 应用账号密码：保证四类字符齐全的强密码。"""
    # 先各取一个，确保包含大写/小写/数字/符号（满足密码策略）
    chars = [
        secrets.choice(_MYSQL_UPPER),
        secrets.choice(_MYSQL_LOWER),
        secrets.choice(_MYSQL_DIGIT),
        secrets.choice(_MYSQL_SPECIAL),
    ]
    pool = _MYSQL_UPPER + _MYSQL_LOWER + _MYSQL_DIGIT + _MYSQL_SPECIAL
    chars += [secrets.choice(pool) for _ in range(length - len(chars))]
    # Fisher-Yates 洗牌，避免"第一个字符必是大写"这类可预测规律
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def gen_minio_secret(length: int = 40) -> str:
    """MinIO SECRET_KEY：40 字符（MinIO 允许的上限），Base64 风格。"""
    pool = string.ascii_letters + string.digits + _MINIO_SPECIAL
    return "".join(secrets.choice(pool) for _ in range(length))


def gen_access_key() -> str:
    """MinIO ACCESS_KEY：短、无特殊字符（会出现在 endpoint 路径与日志中）。"""
    return "invoice" + "".join(secrets.choice(string.ascii_lowercase + string.digits)
                               for _ in range(6))


def gen_deepseek_key_format() -> str:
    """仅用于说明 DeepSeek Key 的格式 —— 真实 Key 只能在平台申请，无法本地生成。"""
    return "sk-" + "".join(secrets.choice(string.ascii_letters + string.digits)
                           for _ in range(32))


# ---------------------------------------------------------------- 输出


def build_lines() -> list[str]:
    """生成一份可直接粘贴进 .env 的键值对。"""
    mysql_pwd = gen_mysql_password()
    # 注意：数据库名/用户/主机不含特殊字符，密码已确保 URL 安全，故无需 urlencode。
    db_url = (
        f"mysql+pymysql://invoice:{mysql_pwd}"
        f"@127.0.0.1:3306/invoice_audit?charset=utf8mb4"
    )
    lines = [
        f"JWT_SECRET={gen_jwt_secret()}",
        f"MINIO_ACCESS_KEY={gen_access_key()}",
        f"MINIO_SECRET_KEY={gen_minio_secret()}",
        f"DATABASE_URL={db_url}",
        "# 同步执行的建库改密语句：",
        f"#   ALTER USER 'invoice'@'localhost' IDENTIFIED BY '{mysql_pwd}';",
        f"#   ALTER USER 'invoice'@'127.0.0.1'  IDENTIFIED BY '{mysql_pwd}';",
    ]
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description="发票审计系统凭据生成器")
    ap.add_argument("--env", action="store_true",
                    help="将生成的键值对追加写入 invoice-audit/.env")
    args = ap.parse_args()

    lines = build_lines()

    print("=" * 62)
    print("  发票审计系统 · 新凭据（请立即保存，关闭终端后无法再查看）")
    print("=" * 62)
    for line in lines:
        print(line)

    print("-" * 62)
    print("  DEEPSEEK_API_KEY 需在 https://platform.deepseek.com/api_keys 申请")
    print("  格式形如：" + gen_deepseek_key_format() + "  （仅示意，非真实可用）")
    print("=" * 62)

    if args.env:
        from pathlib import Path
        env_path = Path(__file__).resolve().parent.parent / "invoice-audit" / ".env"
        if not env_path.exists():
            print(f"\n[错误] 未找到 {env_path}", file=sys.stderr)
            return 1
        with env_path.open("a", encoding="utf-8") as f:
            f.write("\n# ==== 由 tools/gen_secrets.py 生成 ====\n")
            for line in lines:
                if line.startswith("#"):
                    continue
                key = line.split("=", 1)[0]
                f.write(f"{line}\n")
        print(f"\n[完成] 已追加写入 {env_path}（已存在的键需你手工替换）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
