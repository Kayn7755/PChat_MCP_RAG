"""
负责 知识库原文件在本地磁盘上的存取，不管数据库、也不做切分/向量化。
数据库记「有这篇文档」，这里真正保存 PDF/MD 文件本身。

上传 → repos.doc_insert（元数据）
     → document_storage.save_upload（原文件）
     → 解析/切分/chunk_insert（向量）
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
""" 
MD：按标题切，对 title embed
PDF：Docling → 切块 → 对正文 embed
删除顺序：chunk → 文件 → document
写入在 app，检索在 agent 的 RAG tool 
"""
logger = logging.getLogger(__name__)

# base_path 是 所有上传知识库文件的存放根路径
class DocumentStorageService:
    def __init__(self, base_path: str) -> None:
        self._base = Path(base_path).resolve()

    # 把上传字节写到 {base}/{kb_id}/{doc_id}/{uuid}{ext}，返回相对路径
    # filename 原始文件名；主要用来取扩展名（如 .pdf）；可为 None
    # data 上传文件的二进制内容(PDF 本身就是二进制文件); data 只是上传文件的原始字节，save_upload 原样写到磁盘，不会在这里被 Docling 解析。
    def save_upload(self, kb_id: str, document_id: str, filename: str | None, data: bytes) -> str:
        self._base.mkdir(parents=True, exist_ok=True)
        doc_dir = self._base / kb_id / document_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        ext = ""
        if filename and "." in filename:
            ext = filename[filename.rindex(".") :]
        unique = f"{uuid.uuid4()}{ext}"
        target = doc_dir / unique
        target.write_bytes(data)
        rel = "/".join([kb_id, document_id, unique])
        logger.info("文件保存成功 path=%s", rel)
        return rel

    def full_path(self, relative: str) -> Path:
        return (self._base / relative).resolve()

    def delete_file(self, relative: str) -> None:
        p = self.full_path(relative)
        if p.is_file():
            p.unlink()
            logger.info("文件删除成功 %s", relative)
        parent = p.parent
        if parent.is_dir() and not any(parent.iterdir()):
            try:
                parent.rmdir()
            except OSError:
                pass
