# 发票审计系统 · README（交付版）

> 员工上传发票（PDF/JPG/PNG）→ 状态机自动派发 → PP-StructureV3(GPU) 视觉识别+置信度把关 → 规则引擎 + DeepSeek 语言模型双轨审计 → 人工兜底审查 → 终态落库，全流程可视化可追溯。
> 本目录为完整交付包：后端 + 前端 + 控制脚本 + 部署/映射脚本 + 测试套件 + 文档，自包含可运行。

---

## 一、交付清单

```
发票审计系统/
├── README.md                本文件
├── control.sh               控制脚本（启停/状态/修改端口/查IP/日志）
├── start_minio.sh           MinIO 启动脚本（幂等，凭据与 .env 同步）
└── invoice-audit/
    ├── .env / .env.example  全部凭据与参数（.env 不入库）
    ├── deploy.sh            一键部署（幂等）
    ├── stop.sh / status.sh  停后端 / 巡检
    ├── backend/             FastAPI 后端（app/ 分层 + 测试脚本）
    ├── frontend/            Vue3 + Element Plus（dist 已构建，后端静态托管）
    ├── infra/               MySQL 安装 / MinIO 重启 / 端口映射 / 验证脚本
    ├── tests/               测试体系（unit/api/load/ui + 测试报告.md）
    └── 部署说明.md           部署文档
```

## 二、运行环境（本机已就绪）

| 类别 | 依赖 | 说明 |
|---|---|---|
| 操作系统 | Windows 11 + **WSL2 Ubuntu 24.04** | WSL 内执行全部脚本 |
| GPU | NVIDIA 显卡（WSL 内 `nvidia-smi` 可用） | RTX 4070 8GB |
| Python | conda 环境 **SF157**（Python 3.12） | `/conda/miniconda3/envs/SF157` |
| 视觉模型 | paddleocr 3.7 / paddlex 3.7.2 / paddlepaddle-gpu 3.3.1(cu126) | 模型缓存 `~/.paddlex/official_models` |
| 数据库 | **MySQL 8**（库 `invoice_audit`，账号 `invoice@127.0.0.1`） | 可回退 SQLite |
| 对象存储 | MinIO（端口 9000/9001） | 私有桶 + 预签名 URL |
| 语言模型 | DeepSeek API（模型 `deepseek-flash`） | Key 在 .env |
| 后端依赖 | fastapi/uvicorn/sqlalchemy/pymysql/minio/httpx/PyJWT/pyyaml/psutil/pymupdf/python-multipart | deploy.sh 自动补装 |
| 前端 | Node ≥18 + npm（Vue3/Vite/Element Plus） | dist 已构建 |
| 测试工具 | pytest 9 / locust 2.46 / Playwright(本机 Edge) | 可选 |

## 三、使用方法

### 3.1 控制脚本（推荐）

```powershell
# 在 Windows PowerShell 中执行（脚本在 WSL 内运行）
wsl -e bash -lc "tr -d '\r' < C:\Users\35192\Desktop\test\发票审计系统\control.sh | bash -s -- start"     # 一键启动
wsl -e bash -lc "tr -d '\r' < C:\Users\35192\Desktop\test\发票审计系统\control.sh | bash -s -- stop"      # 全部停止
wsl -e bash -lc "tr -d '\r' < C:\Users\35192\Desktop\test\发票审计系统\control.sh | bash -s -- restart"   # 重启
wsl -e bash -lc "tr -d '\r' < C:\Users\35192\Desktop\test\发票审计系统\control.sh | bash -s -- status"    # 巡检
wsl -e bash -lc "tr -d '\r' < C:\Users\35192\Desktop\test\发票审计系统\control.sh | bash -s -- port 8080" # 修改端口为8080并重启
wsl -e bash -lc "tr -d '\r' < C:\Users\35192\Desktop\test\发票审计系统\control.sh | bash -s -- lanip"      # 查当前局域网IP
wsl -e bash -lc "tr -d '\r' < C:\Users\35192\Desktop\test\发票审计系统\control.sh | bash -s -- logs"       # 尾随后端日志
```

### 3.2 首次安装（只需一次）

```powershell
wsl -u root bash -c "tr -d '\r' < /mnt/c/Users/35192/Desktop/test/发票审计系统/invoice-audit/infra/install_mysql.sh | bash"
```

### 3.3 访问与账号

| 入口 | 地址 |
|---|---|
| 系统主页 | http://localhost:8000（局域网映射后可用 http://<本机IP>:8000） |
| API 文档 | http://localhost:8000/docs |
| 审查员/管理员 | 工号 `admin` 密码 `admin`（首登提示改密） |
| 员工 | 登录页"员工注册"自建（工号 8 位字母数字） |

### 3.4 局域网访问（可选）

```powershell
# Windows PowerShell（管理员，弹 UAC 点“是”）：自动探测当前 IP，映射 8000/9000/9001 + 防火墙放行
powershell -ExecutionPolicy Bypass -File C:\Users\35192\Desktop\test\发票审计系统\invoice-audit\infra\lan_expose.ps1
# 下线清理
powershell -ExecutionPolicy Bypass -File C:\Users\35192\Desktop\test\发票审计系统\invoice-audit\infra\offline_cleanup.ps1
```
> 原图预签名 URL 按访问来源自动适配（localhost 访问用 127.0.0.1:9000，局域网 IP 访问用同 IP:9000），无需手工改配置。

## 四、项目架构

```
backend/app/
├── main.py            入口：建库/种子账号/启动状态机 worker/前端静态托管
├── config.py          环境变量读取（.env 经 uvicorn --env-file 注入）
├── database.py        SQLAlchemy 引擎（MySQL 生产 / SQLite 回退，一行切换）
├── models.py          users / claims / configs / audit_logs 四表 ORM
├── schemas.py         Pydantic 请求/响应模型
├── security.py        pbkdf2(60万轮) 哈希 + JWT + 角色鉴权 + 登录限流
├── runtime_config.py  调参热更新中心（vision/llm/rules/enums，DB 持久化）
├── api/               auth / claims / review / config_api / monitor / dashboard
├── services/
│   ├── minio_service.py    存储封装（内部/对外双客户端，预签名 Host 自适应）
│   ├── ocr_service.py      PP-StructureV3 + PDF文本层融合 + 字段清洗 + 置信度聚合
│   ├── llm_service.py      DeepSeek 两轮工具调用（get_claim_info → submit_verdict）
│   └── rules.py            报销规则引擎（确定性规则，代码计算可解释）
└── workers/dispatcher.py   状态机：2s 轮询 + 原子领取 + 10分钟租约回收 + OCR/LLM 线程池
```

## 五、项目流程（状态机）

```
员工上传(≤20文件/一批次) ──► MinIO ──► claims(flow=1, queue=1)
                                        │ 状态机轮询(2s) 原子领取(queue=0 + 租约)
                                        ▼
                              PP-StructureV3(GPU) 识别+清洗+置信度
                                        │ 置信度<阈值 或 关键字段缺失 → flow=3 待人工
                                        ▼ flow=2
                              规则引擎(过期/抬头/重复/算术/敏感/限额)
                                  硬不过→不报销(跳过LLM)；超限→人工
                                        ▼
                          DeepSeek 工具调用两轮：get_claim_info → submit_verdict
                              0报销 / 1不报销 / 2无法判断→flow=3 人工
                                        ▼
                              审查员判定 → flow=0 终态（写审计日志）
```

状态枚举：
- `flow_status`: 0已处理 / 1待处理 / 2视觉已处理 / 3待人工审查 / 4失败（可看板重派）
- `reimb_result`: 0报销 / 1不报销 / 2处理中
- `exception_type`: 0无 / 1视觉置信度低 / 2LLM无法判断 / 3系统故障
- `queue_state`: 0处理中(锁) / 1待分发 / 2完成

## 六、数据库表单字段

### users（员工/审查员，原"员工表+密码表"合并）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK | 主键 |
| emp_no | VARCHAR(32) UNIQUE | 员工工号（8位字母数字，admin 为审查员） |
| name | VARCHAR(64) | 姓名 |
| password_hash | VARCHAR(256) | 密码哈希（pbkdf2$迭代$盐$摘要，**不存明文**） |
| role | VARCHAR(16) | employee / admin |
| department | VARCHAR(64) | 部门（注册时枚举选择） |
| job_level | VARCHAR(32) | 职级 |
| position | VARCHAR(64) | 岗位 |
| must_change_password | BOOL | 首登强制改密标记 |
| created_at | DATETIME | 创建时间 |

### claims（报销单，每附件一条，batch_id 聚合同一次上传）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK | 主键 |
| batch_id | VARCHAR(64) | 上传批次号（一次提交的所有文件共享） |
| user_id | INT FK | 所属员工 |
| file_key | VARCHAR(512) | MinIO 对象键（{工号}/{批次}/{序号}_{文件名}） |
| file_name / file_type / file_size | - | 文件名 / jpg·png·pdf / 大小 |
| flow_status | INT | 流程状态 0/1/2/3/4 |
| reimb_result | INT | 报销结果 0/1/2 |
| exception_type | INT | 异常类型 0/1/2/3 |
| queue_state | INT | 队列状态 0/1/2 |
| lock_owner / lock_acquired_at | - | 分布式锁（租约10分钟自动回收） |
| ocr_text | JSON | 清洗后的发票键值对（类型/号码/日期/购销方/金额/税额/明细等） |
| ocr_conf | FLOAT | 聚合置信度 |
| rule_check | JSON | 规则引擎结论（hard_fail/warnings/needs_review） |
| user_note | TEXT | 员工提交备注 |
| model_note | TEXT | 模型返回备注 |
| reviewer_note | TEXT | 审查员返回备注 |
| submitted_at / processed_at / updated_at | DATETIME | 时间戳 |

### configs（调参表，key→JSON，改后即时生效）
| 字段 | 说明 |
|---|---|
| key UNIQUE | vision / llm / rules / enums 四区块 |
| value JSON | 各区块参数（见下方"调参"） |
| updated_by / updated_at | 修改人与时间 |

### audit_logs（审计日志）
| 字段 | 说明 |
|---|---|
| operator / action / table_name / row_id | 操作人 / 动作(register·review·requeue·dashboard_edit·update_config·change_password) / 表 / 行 |
| before_json / after_json | 修改前后快照 |
| created_at | 时间 |

> 原设计中的"人工审查队列表"不建表（= claims 按 flow_status=3 的查询视图）；"密码表"= users 表（密码哈希存储，看板可浏览）。

## 七、技术实现要点

1. **状态机可靠性**：`UPDATE ... WHERE queue_state=1` 原子领取（并发安全）；锁租约 10 分钟超时回收（worker 崩溃自动救回，已实测）
2. **双模型 + 人工兜底**：确定性规则用代码算（可解释），LLM 只做语义判断；视觉低置信度/关键字段缺失/LLM 无法判断 → 自动转人工
3. **PDF 双通道**：电子发票优先合并自带文本层（权威零误差），扫描件 GPU OCR
4. **LLM 工具调用**：DeepSeek 非思考模式 + 强制 tool_choice 两轮（get_claim_info → submit_verdict），服务端强校验参数
5. **安全**：pbkdf2 哈希、JWT、登录限流、上传魔数校验+文件名净化、MinIO 私有桶、密钥不回显、审计日志
6. **可观测**：监控 CPU/GPU/显存/内存/磁盘/DB/MinIO（缓存优化 2ms）；看板可浏览全表数据并可修正

## 八、环境变量说明（.env，修改后重启后端生效）

| 变量 | 默认 | 说明 |
|---|---|---|
| DEEPSEEK_API_KEY | - | DeepSeek API 密钥 |
| DEEPSEEK_BASE_URL | https://api.deepseek.com/v1 | 语言模型地址 |
| DEEPSEEK_MODEL | deepseek-flash | 模型名（官方现役） |
| MINIO_ENDPOINT | 127.0.0.1:9000 | 内部访问地址 |
| MINIO_PUBLIC_ENDPOINT | 127.0.0.1:9000 | 对外预签名地址（域名场景用；本机/局域网自动适配） |
| MINIO_ACCESS_KEY / SECRET | - | 与 start_minio.sh 同步 |
| MINIO_BUCKET | reimb-invoices | 桶名 |
| DATABASE_URL | mysql+pymysql://... | 生产 MySQL；回退 sqlite:///... |
| APP_HOST / APP_PORT | 0.0.0.0 / 8000 | 监听地址/端口（`control.sh port` 可改） |
| JWT_SECRET | - | 登录态签名密钥（≥32字节） |
| JWT_EXPIRE_MINUTES | 720 | 登录有效期（分钟） |
| UPLOAD_MAX_FILES / SIZE | 20 / 20MB | 上传限制 |
| OCR_WORKERS / LLM_WORKERS | 1 / 2 | 状态机并发（OCR 受显存限制） |

调参页可改（configs 表，即时生效）：vision（置信度阈值/聚合权重/设备/缩放）、llm（模型/温度/系统提示词）、rules（公司主体/有效期/额度/敏感品类/开关）、enums（部门/职级/岗位选项）。

## 九、部署实现

- `deploy.sh`：MinIO 启动 → MySQL 检查 → 依赖补装 → 前端检查 → 后端 nohup 启动 → 健康检查（全部幂等）
- `control.sh`：统一入口（start/stop/restart/status/port/lanip/logs）
- `infra/install_mysql.sh`：MySQL 8 安装建库建账号（root 执行一次）
- `infra/lan_expose.ps1`：netsh portproxy 端口映射 + 防火墙（自动探测当前 IP）
- WSL 重启后：跑一次 `control.sh start` 即恢复

## 十、测试与验收

```bash
tr -d '\r' < tests/run_regression.sh | bash   # 全量回归 94 用例
tr -d '\r' < tests/run_load.sh | bash         # locust 压测
node tests/ui/ui_smoke.js                     # UI 冒烟（Windows）
# 完整报告：tests/测试报告.md
```
实测：单元 31/31、API 63/63、压测 4999 请求 0 失败、20 文件管道 56.5s、UI 冒烟 10/10。

## 十一、已知限制

- 照片翻拍/盖章遮挡的增值税票可能漏字段 → 自动转人工（设计行为）
- 单 OCR worker 串行（约 21 张/分钟）；扩容 `OCR_WORKERS`
- 登录约 90ms（pbkdf2 安全成本）；LLM 判定存在波动 → 建议对"报销"结果人工抽检
- MySQL/MinIO 在 WSL 无 systemd，随 WSL 重启停止 → `control.sh start` 恢复
