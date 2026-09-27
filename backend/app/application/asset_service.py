import io
from typing import Any, Dict, List, Optional
from pypdf import PdfReader


class AssetService:
    def __init__(self, assets_repo):
        self.assets_repo = assets_repo

    def create(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.assets_repo.create(user_id, payload)

    def list_for_user(self, user_id: str, question_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.assets_repo.list_for_user(user_id, question_id)

    def get_for_user(self, user_id: str, asset_id: str) -> Optional[Dict[str, Any]]:
        return self.assets_repo.get_for_user(user_id, asset_id)

    def delete(self, user_id: str, asset_id: str) -> bool:
        return self.assets_repo.delete(user_id, asset_id)

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
        """
        if asset_type not in ("NOTE", "SUMMARY", "MNEMONIC"):
            raise ValueError(f"不支持的资料类型: {asset_type}")

        suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if suffix not in {"txt", "md", "markdown", "pdf"}:
            raise ValueError(f"不支持的文件格式（.{suffix}），仅支持 PDF、Markdown 与纯文本资料")

        if suffix in {"txt", "md", "markdown"}:
            try:
                extracted_text = content.decode("utf-8").strip()
            except UnicodeDecodeError as exc:
                raise ValueError("文本文件必须使用 UTF-8 编码") from exc
            if not extracted_text:
                raise ValueError("文件内容为空")
        elif suffix == "pdf":
            try:
                stream = io.BytesIO(content)
                reader = PdfReader(stream)
                extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
            except Exception as exc:
                raise ValueError("PDF 文件已损坏或无法解析") from exc
            if not extracted_text:
                raise ValueError("纯图片或扫描版 PDF 无法提取文本，系统不自动 OCR，请提供可提取文本的文档")

        payload = {
            "asset_type": asset_type,
            "content": extracted_text,
            "question_id": question_id,
            "knowledge_tag_id": knowledge_tag_id,
        }
        return self.assets_repo.create(user_id, payload)
