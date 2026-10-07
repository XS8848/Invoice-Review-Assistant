# -*- coding: utf-8 -*-
"""MinIO 对象存储封装：桶初始化、上传、下载、预签名 URL。"""
import pathlib
from datetime import timedelta

from minio import Minio

from .. import config

_client: Minio | None = None
_public_client: Minio | None = None


def get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            config.MINIO_ENDPOINT,
            access_key=config.MINIO_ACCESS_KEY,
            secret_key=config.MINIO_SECRET_KEY,
            secure=config.MINIO_SECURE,
        )
    return _client


def _get_public_client() -> Minio:
    """按对外地址签名预签名 URL（局域网/外网浏览器才能访问原图）。"""
    global _public_client
    if _public_client is None:
        _public_client = Minio(
            config.MINIO_PUBLIC_ENDPOINT,
            access_key=config.MINIO_ACCESS_KEY,
            secret_key=config.MINIO_SECRET_KEY,
            secure=config.MINIO_SECURE,
        )
    return _public_client


def ensure_bucket() -> None:
    client = get_client()
    if not client.bucket_exists(config.MINIO_BUCKET):
        client.make_bucket(config.MINIO_BUCKET)
        client.set_bucket_policy(config.MINIO_BUCKET, _private_policy(config.MINIO_BUCKET))


def _private_policy(bucket: str) -> str:
    # 默认私有：仅支持预签名 URL 访问
    return (
        '{"Version":"2012-10-17","Statement":[{"Effect":"Deny","Principal":{"AWS":["*"]},'
        f'"Action":["s3:GetObject"],"Resource":["arn:aws:s3:::{bucket}/*"],'
        '"Condition":{"StringNotEquals":{"aws:Referer":["internal"]}}}]}'
    )


def put_file(local_path: pathlib.Path, object_key: str, content_type: str = "") -> None:
    client = get_client()
    client.fput_object(
        config.MINIO_BUCKET,
        object_key,
        str(local_path),
        content_type=content_type or "application/octet-stream",
    )


def download_file(object_key: str, local_path: pathlib.Path) -> None:
    client = get_client()
    client.fget_object(config.MINIO_BUCKET, object_key, str(local_path))


def remove_file(object_key: str) -> None:
    client = get_client()
    client.remove_object(config.MINIO_BUCKET, object_key)


def _client_for_endpoint(endpoint: str) -> Minio:
    return Minio(
        endpoint,
        access_key=config.MINIO_ACCESS_KEY,
        secret_key=config.MINIO_SECRET_KEY,
        secure=config.MINIO_SECURE,
    )


def presigned_url(object_key: str, public_endpoint: str | None = None,
                  expires_seconds: int = 300) -> str:
    """生成预签名 URL。public_endpoint 为对外地址（未传则用 MINIO_PUBLIC_ENDPOINT）。"""
    endpoint = public_endpoint or config.MINIO_PUBLIC_ENDPOINT
    client = _client_for_endpoint(endpoint)
    return client.presigned_get_object(
        config.MINIO_BUCKET, object_key, expires=timedelta(seconds=expires_seconds)
    )


def presigned_url_for_host(object_key: str, host: str, expires_seconds: int = 300) -> str:
    """按访问来源 Host 自适应生成预签名 URL：
    - 本机访问（localhost/127.0.0.1）→ 127.0.0.1:9000
    - 局域网 IP 访问 → 同 IP:9000（依赖 Windows 端口映射）
    - 域名访问 → 使用 MINIO_PUBLIC_ENDPOINT
    """
    import re as _re

    h = (host or "").split(":")[0].strip()
    if h in ("localhost", "127.0.0.1") or _re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", h):
        return presigned_url(object_key, public_endpoint=f"{h}:9000", expires_seconds=expires_seconds)
    return presigned_url(object_key, expires_seconds=expires_seconds)


def is_healthy() -> bool:
    try:
        return get_client().bucket_exists(config.MINIO_BUCKET)
    except Exception:
        return False
