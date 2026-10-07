# -*- coding: utf-8 -*-
"""Pydantic 请求/响应模型。"""
from datetime import datetime

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    emp_no: str = Field(pattern=r"^[A-Za-z0-9]{8}$", description="8位字母或数字")
    name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=64)
    department: str = ""
    job_level: str = ""
    position: str = ""


class LoginIn(BaseModel):
    emp_no: str
    password: str


class ChangePasswordIn(BaseModel):
    emp_no: str
    old_password: str
    new_password: str = Field(min_length=6, max_length=64)


class UserOut(BaseModel):
    id: int
    emp_no: str
    name: str
    role: str
    department: str
    job_level: str
    position: str
    must_change_password: bool = False

    class Config:
        from_attributes = True


class ClaimOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    batch_id: str
    user_id: int
    emp_no: str = ""
    emp_name: str = ""
    department: str = ""
    job_level: str = ""
    position: str = ""
    file_name: str
    file_type: str
    file_size: int
    flow_status: int
    reimb_result: int
    exception_type: int
    queue_state: int
    ocr_text: dict | None = None
    ocr_conf: float | None = None
    rule_check: dict | None = None
    user_note: str = ""
    model_note: str = ""
    reviewer_note: str = ""
    submitted_at: datetime | None = None
    processed_at: datetime | None = None


class ReviewIn(BaseModel):
    result: int = Field(ge=0, le=1, description="0报销 1不报销")
    note: str = ""


class ConfigPutIn(BaseModel):
    section: str
    value: dict


class DashboardEditIn(BaseModel):
    reimb_result: int | None = None
    flow_status: int | None = None
    model_note: str | None = None
    reviewer_note: str | None = None
