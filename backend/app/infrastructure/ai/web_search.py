"""Replaceable web-search boundary with an explicit offline state."""
import json
import os
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request


class WebSearchAdapter:
    name: str = "base"

    def search(self, query: str) -> Dict[str, Any]:
        raise NotImplementedError


class OpenWebSearchAdapter(WebSearchAdapter):
    """Default local open-webSearch adapter.

    Connects to local open-webSearch service endpoint if available,
    or falls back gracefully to UNAVAILABLE offline state.
    """
    def __init__(self, endpoint_url: Optional[str] = None):
        self.name = "open-webSearch"
        self.endpoint_url = endpoint_url or os.environ.get("OPEN_WEBSEARCH_URL", "http://localhost:8000/v1/search")

    def search(self, query: str) -> Dict[str, Any]:
        req = urllib.request.Request(
            self.endpoint_url,
            data=json.dumps({"query": query}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "status": "VERIFIED",
                    "message": data.get("message") or f"通过 open-webSearch 检索到 {len(data.get('results', []))} 条依据。",
                    "results": data.get("results", []),
                }
        except Exception:
            return {
                "status": "UNAVAILABLE",
                "message": "当前未配置可用联网核查服务或连接超时，未取得外部证据。",
                "results": [],
            }


class OfflineWebSearch(WebSearchAdapter):
    def __init__(self):
        self.name = "offline"

    def search(self, query: str) -> Dict[str, Any]:
        return {
            "status": "UNAVAILABLE",
            "message": "当前未配置联网核查服务，未取得外部证据。",
            "results": [],
        }


def get_web_search_adapter(provider_type: Optional[str] = None) -> WebSearchAdapter:
    provider = provider_type or os.environ.get("WEB_SEARCH_PROVIDER", "open-webSearch")
    if provider == "open-webSearch":
        return OpenWebSearchAdapter()
    elif provider == "offline":
        return OfflineWebSearch()
    return OfflineWebSearch()
