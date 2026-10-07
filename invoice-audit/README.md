# 发票审计系统（invoice-audit）

> 发票上传 → MinIO 存储 → PP-StructureV3 视觉识别（置信度把关）→ DeepSeek 语言模型审计（规则引擎 + 工具调用）→ 人工兜底审查 → 终态落库。
> 前端 Vue3 + Element Plus；后端 FastAPI + SQLAlchemy；**生产数据库 MySQL 8**（可回退 SQLite）；全部运行于 WSL2（conda SF157 + RTX 4070）。

## 架构与状态机

```
员工上传(≤20文件/一批次) ──► MinIO ──► claims(flow=1, queue=1)
                                        │ 状态机轮询(2s)原子领取(queue=0, 租约10min)
                                        ▼
                              PP-StructureV3(GPU) 识别+清洗+置信度
                                        │ 置信度<阈值 或 关键字段缺失 → flow=3 待人工
                                        ▼ flow=2
                              规则引擎(确定性规则) 硬不过→不报销；超限→人工/不报销
                                        ▼
                       DeepSeek deepseek-flash 两轮工具调用
                          get_claim_info → submit_verdict
                            0报销 / 1不报销 / 2无法判断→flow=3 人工
                                        ▼
                              审查员判定 → flow=0 终态
```

状态枚举：
- `flow_status`: 0已处理 / 1待处理 / 2视觉已处理 / 3待人工审查 / 4失败（可看板重派）
- `reimb_result`: 0报销 / 1不报销 / 2处理中
- `exception_type`: 0无 / 1视觉置信度低 / 2LLM无法判断 / 3系统故障
- `queue_state`: 0处理中(锁) / 1待分发 / 2完成

## 一键部署（幂等，可重复执行）

```powershell
# 首次：安装 MySQL 8 并建库建账号（只需一次）
wsl -u root bash -c "tr -d '\r' < /mnt/c/Users/35192/Desktop/test/发票审计系统/invoice-audit/infra/install_mysql.sh | bash"

# 一键部署：MinIO + MySQL + 依赖 + 前端 + 后端 + 健康检查
wsl -e bash -lc "tr -d '\r' < /mnt/c/Users/35192/Desktop/test/发票审计系统/invoice-audit/deploy.sh | bash"

# 运维
wsl -e bash -lc "tr -d '\r' < /mnt/c/Users/35192/Desktop/test/发票审计系统/invoice-audit/status.sh | bash"   # 巡检
wsl -e bash -lc "tr -d '\r' < /mnt/c/Users/35192/Desktop/test/发票审计系统/invoice-audit/stop.sh | bash"     # 停后端
```

访问：Windows `http://localhost:8000` · 局域网 `http://172.18.28.205:8000` · API 文档 `/docs`
审查员：`admin / admin`（首登改密）。员工在前端注册（8位字母数字工号）。

> WSL 重启后执行一次 `deploy.sh` 即可拉起全部服务（MinIO/MySQL 均无 systemd，脚本幂等处理）。

## 配置（调参页 / configs 表，改后即时生效）

| 区块 | 关键参数 |
|---|---|
| vision | `device`、`conf_threshold`(0.75)、`agg_weights`[0.8,0.2]、`max_side` |
| llm | `model`(deepseek-flash)、`base_url`、`temperature`、`system_prompt` |
| rules | `company_name`/`company_tax_id`（抬头校验基准，**上线必填**）、`max_age_days`、`deduplicate_no`、`check_arithmetic`、`sensitive_categories`、`per_claim_limit`、`per_month_limit` + `per_month_limit_action`(review/reject)、`hard_fail_skips_llm` |
| enums | 部门/职级/岗位下拉选项 |

进程级参数在 `.env`：`OCR_WORKERS`(默认1，受GPU显存限制) / `LLM_WORKERS`(默认2，受API并发限制)。

## 报销规则引擎（确定性规则，代码计算，可解释）

1. 票面要素完整性（号码/日期/价税合计缺失 → 不报销）
2. 重复报销（同发票号已有报销记录 → 不报销）
3. 发票有效期（默认 365 天）
4. 抬头校验（个人/与公司主体不符 → 不报销）
5. 金额算术（金额+税额=价税合计）
6. 税率合法性（非常规税率 → 预警）
7. 敏感品类（餐饮/烟酒/礼品等：无备注 → 不报销；有备注 → 预警交 LLM）
8. 限额：单笔超限 → 转人工；**当月累计超限 → 转人工或直接不报销（可配）**

## 安全加固（生产部署版）

- 密码 pbkdf2_hmac(60万轮)；JWT 登录态；**登录限流**（同工号 1 分钟 5 次）
- **MinIO 凭据与 JWT_SECRET 已随机化**（`start_minio.sh` 与 `.env` 同步）
- **MySQL 专用账号** `invoice@127.0.0.1`（非 root），utf8mb4
- 上传白名单+魔数校验+大小限制；MinIO 私有 bucket + 预签名 URL
- LLM 工具参数服务端强校验；全部管理操作写审计日志；admin 首登强制改密

## 功能清单

- 员工：注册/登录/改密、批次化上传（≤20文件）、实时进度（5 步）、历史按批次聚合、原图查看、撤销
- 审查员：待人工队列、工作区（原图+员工信息+OCR字段+规则结论+模型备注）、同批次其他文件上下文、报销/不报销判定、返回备注
- 管理员：模型调参（视觉/语言/规则/枚举）、系统监控（CPU/GPU/显存/内存/磁盘/DB/MinIO）、数据看板（全表+统计+历史结果修正+**重新派发**+审计日志）

## 关键 API

```
POST /api/auth/register|login|change-password   认证（login 有限流）
POST /api/claims              上传（multipart，≤20文件，自动成批）
GET  /api/claims/mine         我的历史（含批次）
GET  /api/claims/batch/{id}   批次内文件（聚合审查上下文）
GET  /api/claims/{id}/file    原图（预签名 302）
DELETE /api/claims/{id}       撤销
GET  /api/review/queue        待人工队列
POST /api/review/{id}         审查员判定
GET/PUT /api/config           调参（vision/llm/rules/enums）
GET  /api/monitor             系统监控
GET  /api/dashboard/*         看板/统计/修正/重派/审计日志
PUT  /api/dashboard/claims/{id}/requeue   失败或历史单据重新派发
```

## 测试与验收

```bash
# 后端目录（WSL 内执行）
tr -d '\r' < run_test_ocr.sh | bash     # OCR 5 样本字段+置信度
tr -d '\r' < run_llm_test.sh | bash     # LLM 三用例工具调用
tr -d '\r' < run_e2e.sh | bash          # 全链路 E2E（含限流/月限额/重派）
```

实测 5 张真实发票覆盖全部分支：硬规则×2（过期/个人抬头）、LLM 判定×1、LLM 无法判断→人工×1、视觉关键字段缺失→人工×1，另验证登录限流 429、月限额硬拦截、重派后重新走完流程。

## 已知限制（如实披露）

- 照片翻拍/盖章遮挡的增值税票可能漏字段 → 自动转人工（设计行为）
- OCR 串行受 `OCR_WORKERS` 控制（GPU 显存 8GB 建议 1-2）
- 月累计限额统计范围为"当月已报销（result=0）"，人工修正后自动纳入
- MySQL 在 WSL 内无 systemd，重启 WSL 后跑 `deploy.sh` 自动拉起
