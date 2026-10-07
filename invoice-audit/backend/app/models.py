# -*- coding: utf-8 -*-
"""数据模型。

语义修正（见可行性分析文档）：
- 原“员工表/密码表”合并为 users（密码只存哈希，档案不重复）；
- 原“人工审查队列表”不建表，审查队列 = SELECT claims WHERE flow_status=3；
- 工作流字段全部属于报销单 claims，不属于员工。
"""
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    """员工 / 审查员（admin）。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    emp_no: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="employee", nullable=False)  # employee|admin
    department: Mapped[str] = mapped_column(String(64), default="")
    job_level: Mapped[str] = mapped_column(String(32), default="")
    position: Mapped[str] = mapped_column(String(64), default="")
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    claims = relationship("Claim", back_populates="user")


class Claim(Base):
    """报销单（每附件一条，batch_id 聚合同一次上传）。"""

    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)

    # 附件（MinIO）
    file_key: Mapped[str] = mapped_column(String(512), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0)

    # 流程状态：0已处理 1待处理 2视觉已处理 3待人工审查 4失败
    flow_status: Mapped[int] = mapped_column(Integer, default=1, index=True)
    # 报销结果：0报销 1不报销 2处理中
    reimb_result: Mapped[int] = mapped_column(Integer, default=2)
    # 异常类型：0无 1视觉置信度低 2LLM无法判断 3系统故障
    exception_type: Mapped[int] = mapped_column(Integer, default=0)
    # 队列状态：0处理中(锁) 1待分发 2完成
    queue_state: Mapped[int] = mapped_column(Integer, default=1, index=True)
    lock_owner: Mapped[str] = mapped_column(String(64), default="", nullable=True)
    lock_acquired_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # OCR 结果
    ocr_text: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # 清洗后键值对
    ocr_conf: Mapped[float | None] = mapped_column(Float, nullable=True)  # 聚合置信度
    rule_check: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 规则引擎结论

    # 备注（原文同名两列已拆开）
    user_note: Mapped[str] = mapped_column(Text, default="")       # 员工提交备注
    model_note: Mapped[str] = mapped_column(Text, default="")      # 模型返回备注
    reviewer_note: Mapped[str] = mapped_column(Text, default="")   # 审查员返回备注

    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("User", back_populates="claims")


class AppConfig(Base):
    """调参表（key -> JSON）。视觉参数 / 语言参数 / 报销规则 / 枚举选项。"""

    __tablename__ = "configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(32), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class AuditLog(Base):
    """审计日志（数据看板改动历史可追溯）。"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operator: Mapped[str] = mapped_column(String(32), default="")
    action: Mapped[str] = mapped_column(String(32), default="")
    table_name: Mapped[str] = mapped_column(String(64), default="")
    row_id: Mapped[int] = mapped_column(Integer, default=0)
    before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
