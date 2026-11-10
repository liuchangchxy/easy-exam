import io
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from pypdf import PdfReader

ALLOWED_ASSET_TYPES = {"NOTE", "SUMMARY", "MNEMONIC"}

_ASSET_MIME_TYPES = {
    "pdf": "application/pdf",
    "md": "text/markdown",
    "markdown": "text/markdown",
    "txt": "text/plain",
}


class AssetService:
    def __init__(self, assets_repo, storage_dir: str | Path | None = None):
        self.assets_repo = assets_repo
        base_dir = Path(storage_dir) if storage_dir is not None else Path(self.assets_repo.db_path).resolve().parent / "asset_files"
        self.storage_dir = Path(base_dir)

    def create(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if payload.get("asset_type") not in ALLOWED_ASSET_TYPES:
            raise ValueError(f"不支持的资料类型: {payload.get('asset_type')}")
        content = str(payload.get("content") or "").strip()
        if not content:
            raise ValueError("资料内容不能为空")
        safe_payload = {**payload, "content": content}
        return self.assets_repo.create(user_id, safe_payload)

    def list_for_user(self, user_id: str, question_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.assets_repo.list_for_user(user_id, question_id)

    def get_for_user(self, user_id: str, asset_id: str) -> Optional[Dict[str, Any]]:
        return self.assets_repo.get_for_user(user_id, asset_id)

    def update(self, user_id: str, asset_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        existing = self.assets_repo.get_for_user(user_id, asset_id)
        if not existing:
            raise LookupError("asset not found")

        changes: Dict[str, Any] = {}
        if "asset_type" in payload and payload["asset_type"] is not None:
            if payload["asset_type"] not in ALLOWED_ASSET_TYPES:
                raise ValueError(f"不支持的资料类型: {payload['asset_type']}")
            changes["asset_type"] = payload["asset_type"]
        if "content" in payload and payload["content"] is not None:
            content = str(payload["content"]).strip()
            if not content:
                raise ValueError("资料内容不能为空")
            changes["content"] = content

        updated = self.assets_repo.update(user_id, asset_id, changes)
        if not updated:
            raise LookupError("asset not found")
        return updated

    def delete(self, user_id: str, asset_id: str) -> bool:
        existing = self.assets_repo.get_for_user(user_id, asset_id)
        if not existing:
            return False
        deleted = self.assets_repo.delete(user_id, asset_id)
        if deleted:
            self._remove_stored_file(existing.get("storage_key"))
        return deleted

    def get_file(self, user_id: str, asset_id: str) -> Optional[Dict[str, Any]]:
        asset = self.assets_repo.get_for_user(user_id, asset_id)
        if not asset:
            return None
        storage_key = asset.get("storage_key")
        if not storage_key:
            return None
        path = self._resolve_storage_path(storage_key)
        if path is None or not path.is_file():
            return None
        return {
            "path": path,
            "file_name": asset.get("file_name") or path.name,
            "mime_type": asset.get("mime_type") or _ASSET_MIME_TYPES.get(path.suffix.lstrip(".").lower(), "application/octet-stream"),
        }

    def create_from_file(
        self,
        user_id: str,
        filename: str,
        content: bytes,
        asset_type: str = "NOTE",
        question_id: Optional[str] = None,
        knowledge_tag_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Pre-check and extract text from uploaded reference materials (PDF, Markdown, Text).

        Rejects corrupt files, image-only PDFs (no automatic OCR), and unsupported extensions.
        The original upload is retained so the user can preview or download it later.
        """
        if asset_type not in ALLOWED_ASSET_TYPES:
            raise ValueError(f"不支持的资料类型: {asset_type}")

        original_name = Path(str(filename or "").replace("\\", "/")).name
        suffix = original_name.lower().rsplit(".", 1)[-1] if "." in original_name else ""
        if suffix not in {"txt", "md", "markdown", "pdf"}:
            raise ValueError(f"不支持的文件格式（.{suffix}），仅支持 PDF、Markdown 与纯文本资料")

        if suffix in {"txt", "md", "markdown"}:
            try:
                extracted_text = content.decode("utf-8").strip()
            except UnicodeDecodeError as exc:
                raise ValueError("文本文件必须使用 UTF-8 编码") from exc
            if not extracted_text:
                raise ValueError("文件内容为空")
        else:
            try:
                stream = io.BytesIO(content)
                reader = PdfReader(stream)
                extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
            except Exception as exc:
                raise ValueError("PDF 文件已损坏或无法解析") from exc
            if not extracted_text:
                raise ValueError("纯图片或扫描版 PDF 无法提取文本，系统不自动 OCR，请提供可提取文本的文档")

        storage_key = f"{uuid.uuid4().hex}.{suffix}"
        stored_path = self._resolve_storage_path(storage_key)
        if stored_path is None:
            raise RuntimeError("asset storage directory is not available")
        stored_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = stored_path.with_suffix(stored_path.suffix + ".tmp")
        try:
            temporary_path.write_bytes(content)
            os.replace(temporary_path, stored_path)
        except Exception as exc:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise ValueError("文件保存失败，请稍后重试") from exc

        payload = {
            "asset_type": asset_type,
            "content": extracted_text,
            "question_id": question_id,
            "knowledge_tag_id": knowledge_tag_id,
            "file_name": original_name,
            "mime_type": _ASSET_MIME_TYPES.get(suffix, mimetypes.guess_type(original_name)[0] or "application/octet-stream"),
            "storage_key": storage_key,
        }
        try:
            return self.assets_repo.create(user_id, payload)
        except Exception:
            try:
                stored_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def _resolve_storage_path(self, storage_key: str | None) -> Path | None:
        if not storage_key:
            return None
        candidate = (self.storage_dir / Path(storage_key).name).resolve()
        try:
            candidate.relative_to(self.storage_dir.resolve())
        except ValueError:
            return None
        return candidate

    def _remove_stored_file(self, storage_key: str | None) -> None:
        path = self._resolve_storage_path(storage_key)
        if path is None:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
