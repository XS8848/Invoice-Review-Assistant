#!/usr/bin/env bash
# ============================================================
#  GitHub 推送诊断脚本
#  在网络受限环境下定位推送失败原因
#
#  用法：bash tools/git_push_doctor.sh
# ============================================================
set -u

REPO="${1:-git@github.com:OWNER/REPO.git}"
SSH_HOST="${SSH_HOST:-ssh.github.com}"

red()   { echo -e "\033[31m$1\033[0m"; }
green() { echo -e "\033[32m$1\033[0m"; }
yellow(){ echo -e "\033[33m$1\033[0m"; }

echo "=============================================="
echo "  GitHub 推送诊断"
echo "  目标：$REPO"
echo "=============================================="

# ---------- 1. SSH 认证 ----------
echo ""
echo "[1/4] SSH 认证（shell 通道）"
if timeout 20 ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
  green "  ✓ 认证成功"
else
  red "  ✗ 认证失败"
fi

# ---------- 2. SSH git 协议通道 ----------
echo ""
echo "[2/4] SSH git 协议通道（exec）"
GIT_TERMINAL_PROMPT=0 timeout 30 ssh -T git@github.com \
  "git-upload-pack '${REPO##*/}'" >/dev/null 2>&1
if [ $? -eq 0 ]; then
  green "  ✓ git 协议通道正常"
else
  yellow "  ✗ git 协议被拦截（认证通但传输断=典型 DPI 深度检测）"
  echo "    → 改用 HTTPS：git remote set-url origin https://github.com/OWNER/REPO.git"
fi

# ---------- 3. HTTPS 通道 ----------
echo ""
echo "[3/4] HTTPS 通道"
if GIT_TERMINAL_PROMPT=0 timeout 30 git ls-remote \
     "https://github.com/${REPO#git@github.com:}" >/dev/null 2>&1; then
  green "  ✓ HTTPS 可用（推荐通道）"
else
  red "  ✗ HTTPS 也不通"
fi

# ---------- 4. 主机密钥指纹校验 ----------
echo ""
echo "[4/4] 主机密钥指纹校验"
echo "  本机已登记："
ssh-keygen -lf "$HOME/.ssh/known_hosts" 2>/dev/null \
  | grep -E "github\.com" | sed 's/^/    /'
echo ""
echo "  GitHub 官方 ed25519 指纹（务必比对）："
echo "    SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU"
echo ""
echo "  若本机指纹与官方不一致，切勿继续推送（可能被中间人替换）"

echo ""
echo "=============================================="
echo "  凭据配置（HTTPS 推送需要）"
echo "=============================================="
cat <<'GUIDE'
  1) 生成 token：https://github.com/settings/tokens/new
     Note: invoice-push
     Expiration: 按需
     勾选: repo
  2) 执行推送时输入：
     Username: 你的 GitHub 用户名
     Password: 粘贴 token（不是登录密码）
  3) Git Credential Manager 会保存，后续免重复输入

  安全提示：token 等同于账号密码，切勿提交入库或粘贴到聊天窗口。
GUIDE
echo "=============================================="