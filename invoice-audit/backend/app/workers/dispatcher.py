# -*- coding: utf-8 -*-
"""状态机分发 worker：轮询领取（原子 UPDATE）+ 租约回收 + OCR/LLM 线程池。

状态迁移（与可行性分析文档 L2 表一致）：
  员工提交        -> flow=1 queue=1
  视觉领取        -> queue=0
  视觉成功        -> flow=2 queue=1
  视觉置信度低    -> flow=3 exception=1 queue=1
  LLM 领取        -> queue=0
  LLM 判定 0/1    -> flow=0 queue=2 result=0/1
  LLM 无法判断    -> flow=3 exception=2 queue=1
  人工判定        -> flow=0 queue=2 result=0/1
"""
import asyncio
import logging
import socket
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from sqlalchemy import update

from .. import config
from .. import remote as remote_calls
from ..database import SessionLocal
from ..models import Claim, User
from ..runtime_config import get_section
from ..services import minio_service, ocr_service, rules as rules_engine
from ..services.llm_service import run_audit

logger = logging.getLogger("dispatcher")
WORKER_ID = f"{socket.gethostname()}-worker"

POLL_INTERVAL = 2          # 轮询间隔（秒）
LEASE_SECONDS = 600        # 锁租约（秒），超时回收
BATCH_LIMIT = max(4, config.OCR_WORKERS + config.LLM_WORKERS)  # 每轮最多领取条数


class Dispatcher:
    def __init__(self) -> None:
        self._stop = False
        self.ocr_pool = ThreadPoolExecutor(
            max_workers=config.OCR_WORKERS, thread_name_prefix="ocr"
        )
        self.llm_pool = ThreadPoolExecutor(
            max_workers=config.LLM_WORKERS, thread_name_prefix="llm"
        )

    # ---------- 主循环 ----------
    async def loop(self) -> None:
        logger.info("dispatcher loop started")
        while not self._stop:
            try:
                self._dispatch_round()
            except Exception:
                logger.error("dispatch round error:\n%s", traceback.format_exc())
            await asyncio.sleep(POLL_INTERVAL)

    async def lease_reaper(self) -> None:
        while not self._stop:
            try:
                self._reap()
            except Exception:
                logger.error("lease reaper error:\n%s", traceback.format_exc())
            await asyncio.sleep(60)

    def stop(self) -> None:
        self._stop = True
        self.ocr_pool.shutdown(wait=False, cancel_futures=True)
        self.llm_pool.shutdown(wait=False, cancel_futures=True)

    # ---------- 轮询领取 ----------
    def _dispatch_round(self) -> None:
        with SessionLocal() as db:
            rows = (
                db.query(Claim)
                .filter(Claim.queue_state == 1, Claim.flow_status.in_([1, 2]))
                .order_by(Claim.submitted_at.asc())
                .limit(BATCH_LIMIT)
                .all()
            )
        for row in rows:
            self._claim_row(row.id, row.flow_status)

    def _claim_row(self, claim_id: int, flow: int) -> None:
        with SessionLocal() as db:
            stmt = (
                update(Claim)
                .where(Claim.id == claim_id, Claim.queue_state == 1)
                .values(
                    queue_state=0,
                    lock_owner=WORKER_ID,
                    lock_acquired_at=datetime.now(),
                )
            )
            res = db.execute(stmt)
            db.commit()
            if res.rowcount != 1:
                return  # 被其他 worker 抢走
        if flow == 1:
            self.ocr_pool.submit(self._run_ocr, claim_id)
        else:
            self.llm_pool.submit(self._run_llm, claim_id)

    def _reap(self) -> None:
        cutoff = datetime.now() - timedelta(seconds=LEASE_SECONDS)
        with SessionLocal() as db:
            db.execute(
                update(Claim)
                .where(
                    Claim.queue_state == 0,
                    Claim.flow_status.in_([1, 2]),
                    Claim.lock_acquired_at < cutoff,
                )
                .values(queue_state=1, lock_owner="", lock_acquired_at=None)
            )
            db.commit()

    # ---------- 视觉模型任务 ----------
    def _run_ocr(self, claim_id: int) -> None:
        vision_cfg = get_section("vision")
        try:
            with SessionLocal() as db:
                claim = db.get(Claim, claim_id)
                if claim is None or claim.flow_status != 1:
                    return
                file_key, file_type, file_name = claim.file_key, claim.file_type, claim.file_name

            if remote_calls.ocr_remote_available():
                # 分布式模式：HTTP 调用独立 OCR 服务（服务端自行从 MinIO 下载）
                out = remote_calls.call_remote_ocr(file_key)
            else:
                # 内嵌模式：本进程 GPU 推理
                local = config.TEMP_DIR / f"{claim_id}_{file_name}"
                minio_service.download_file(file_key, local)
                try:
                    out = ocr_service.process_file(local, file_type)
                finally:
                    local.unlink(missing_ok=True)

            fields, conf = out["fields"], out["conf"]
            with SessionLocal() as db:
                claim = db.get(Claim, claim_id)
                if claim is None:
                    return
                claim.ocr_text = fields
                claim.ocr_conf = conf
                threshold = float(vision_cfg.get("conf_threshold", 0.85))
                critical_missing = not (
                    fields.get("invoice_no") and fields.get("invoice_date") and fields.get("total_amount")
                )
                if conf < threshold or critical_missing:
                    claim.flow_status = 3
                    claim.exception_type = 1
                    claim.queue_state = 1
                    claim.model_note = (
                        f"视觉识别置信度 {conf:.2f}"
                        + ("（低于阈值）" if conf < threshold else "（关键字段缺失）")
                        + "，转人工复核。"
                    )
                else:
                    claim.flow_status = 2
                    claim.queue_state = 1
                db.commit()
                logger.info("ocr done claim=%s conf=%s flow=%s", claim_id, conf, claim.flow_status)
        except Exception:
            logger.error("ocr job failed claim=%s:\n%s", claim_id, traceback.format_exc())
            self._fail_claim(claim_id, "视觉模型处理异常")

    # ---------- 语言模型任务 ----------
    def _run_llm(self, claim_id: int) -> None:
        rules_cfg = get_section("rules")
        try:
            with SessionLocal() as db:
                claim = db.get(Claim, claim_id)
                if claim is None or claim.flow_status != 2:
                    return
                user = db.get(User, claim.user_id)
                fields = claim.ocr_text or {}
                rr = rules_engine.evaluate(fields, user, claim.user_note or "", rules_cfg, db)
                claim.rule_check = rr.to_dict()
                db.commit()

            hard = rr.hard_fail
            review = rr.needs_review
            if hard and rules_cfg.get("hard_fail_skips_llm", True):
                self._finalize(claim_id, result=1, note="；".join(hard))
                logger.info("llm skipped claim=%s hard_fail=%s", claim_id, hard)
                return
            if review and not hard:
                with SessionLocal() as db:
                    claim = db.get(Claim, claim_id)
                    claim.flow_status = 3
                    claim.exception_type = 2
                    claim.queue_state = 1
                    claim.model_note = "；".join(review)
                    db.commit()
                logger.info("llm skipped claim=%s needs_review=%s", claim_id, review)
                return

            with SessionLocal() as db:
                claim = db.get(Claim, claim_id)
                user = db.get(User, claim.user_id)
                info = {
                    "员工信息": {
                        "工号": user.emp_no,
                        "姓名": user.name,
                        "部门": user.department,
                        "职级": user.job_level,
                        "岗位": user.position,
                    },
                    "发票识别字段": claim.ocr_text or {},
                    "规则引擎结论": claim.rule_check or {},
                    "员工备注": claim.user_note or "",
                    "报销单编号": claim.id,
                }
            if remote_calls.llm_remote_available():
                # 分布式模式：HTTP 调用独立 LLM 服务；服务不可用 → 降级转人工（不丢单）
                try:
                    verdict = remote_calls.call_remote_llm(info, rules_cfg)
                except Exception:
                    logger.error("remote llm failed claim=%s:\n%s", claim_id, traceback.format_exc())
                    verdict = {"result": 2, "note": "语言模型服务不可用，转人工审查"}
            else:
                verdict = run_audit(info, rules_cfg)
            if verdict["result"] == 2:
                with SessionLocal() as db:
                    claim = db.get(Claim, claim_id)
                    claim.flow_status = 3
                    claim.exception_type = 2
                    claim.queue_state = 1
                    claim.model_note = verdict["note"] or "语言模型无法判断，转人工审查"
                    db.commit()
            else:
                self._finalize(claim_id, result=verdict["result"], note=verdict["note"])
            logger.info("llm done claim=%s verdict=%s", claim_id, verdict)
        except Exception:
            logger.error("llm job failed claim=%s:\n%s", claim_id, traceback.format_exc())
            self._fail_claim(claim_id, "语言模型处理异常")

    # ---------- 终态写回 ----------
    def _finalize(self, claim_id: int, result: int, note: str) -> None:
        with SessionLocal() as db:
            claim = db.get(Claim, claim_id)
            if claim is None:
                return
            claim.reimb_result = result
            claim.flow_status = 0
            claim.queue_state = 2
            claim.exception_type = 0
            claim.model_note = (note or "")[:500]
            claim.processed_at = datetime.now()
            db.commit()

    def _fail_claim(self, claim_id: int, reason: str) -> None:
        with SessionLocal() as db:
            claim = db.get(Claim, claim_id)
            if claim is None:
                return
            claim.flow_status = 4
            claim.exception_type = 3
            claim.queue_state = 2
            claim.model_note = f"{reason}，请联系管理员在数据看板重新派发"
            db.commit()


dispatcher = Dispatcher()
