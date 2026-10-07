#!/usr/bin/env bash
# 安装并初始化 MySQL 8（幂等，需 root：wsl -u root bash 本脚本）
set -e
export DEBIAN_FRONTEND=noninteractive

MYSQL_APP_PASSWORD="${MYSQL_APP_PASSWORD:-InvoiceAudit_2026_Str0ng}"

if ! command -v mysql >/dev/null 2>&1; then
  echo "[mysql] installing..."
  apt-get update -qq
  apt-get install -y -qq mysql-server >/dev/null 2>&1
  echo "[mysql] installed: $(mysql --version)"
fi

# 启动（WSL 无 systemd，用 service/mysqld_safe）
if ! mysqladmin ping --silent 2>/dev/null; then
  echo "[mysql] starting..."
  (service mysql start 2>/dev/null || true)
  sleep 6
fi
if ! mysqladmin ping --silent 2>/dev/null; then
  echo "[mysql] fallback mysqld_safe..."
  mkdir -p /var/run/mysqld && chown mysql:mysql /var/run/mysqld
  nohup setsid mysqld_safe --user=mysql >/var/log/mysqld_safe.log 2>&1 &
  sleep 10
fi
mysqladmin ping --silent && echo "[mysql] ping ok" || { echo "[mysql] START FAILED"; exit 1; }

# 建库建账号（幂等）
mysql <<SQL
CREATE DATABASE IF NOT EXISTS invoice_audit CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'invoice'@'localhost' IDENTIFIED BY '${MYSQL_APP_PASSWORD}';
CREATE USER IF NOT EXISTS 'invoice'@'127.0.0.1' IDENTIFIED BY '${MYSQL_APP_PASSWORD}';
GRANT ALL PRIVILEGES ON invoice_audit.* TO 'invoice'@'localhost';
GRANT ALL PRIVILEGES ON invoice_audit.* TO 'invoice'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL
echo "[mysql] database invoice_audit ready, user invoice@127.0.0.1"
echo "MYSQL_APP_PASSWORD=${MYSQL_APP_PASSWORD}"
