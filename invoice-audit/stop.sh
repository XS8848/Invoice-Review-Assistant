#!/usr/bin/env bash
# 停止后端（MinIO/MySQL 保持运行）
pkill -f "uvicorn app.main" && echo "backend stopped" || echo "backend not running"
