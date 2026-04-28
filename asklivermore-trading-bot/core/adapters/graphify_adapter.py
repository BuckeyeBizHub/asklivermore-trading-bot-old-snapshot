"""
core.adapters.graphify_adapter
==============================
Adapter for safishamsi/graphify. Used for persistent memory:
- ticker → past setups
- ticker → trade outcomes
- pattern → win-rate

If Graphify is unreachable, every method returns a degraded stub and logs a warning.
The MemoryGraphAgent surfaces `degraded=True` to the ReasoningAgent.
"""
from __future__ import annotations

from typing import Any

import httpx

from core.config import settings
from core.errors import MemoryUnavailable
from core.logging import get_logger

log = get_logger(__name__)


class GraphifyAdapter:
    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or settings.graphify_url).rstrip("/")
        self.api_key = api_key or settings.graphify_api_key
        self.namespace = settings.graphify_namespace
        self._client = httpx.Client(timeout=10.0)
        self.degraded = False

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _post(self, path: str, payload: dict) -> dict:
        try:
            r = self._client.post(f"{self.base_url}{path}", json=payload, headers=self._headers())
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:
            log.warning("graphify.unreachable", path=path, error=str(e))
            self.degraded = True
            raise MemoryUnavailable(str(e)) from e

    def _get(self, path: str, params: dict | None = None) -> dict:
        try:
            r = self._client.get(f"{self.base_url}{path}", params=params, headers=self._headers())
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:
            log.warning("graphify.unreachable", path=path, error=str(e))
            self.degraded = True
            raise MemoryUnavailable(str(e)) from e

    # ----------------------------- public API ----------------------------- #
    def upsert_node(self, kind: str, key: str, props: dict[str, Any]) -> None:
        try:
            self._post(
                "/nodes",
                {"namespace": self.namespace, "kind": kind, "key": key, "props": props},
            )
        except MemoryUnavailable:
            return

    def add_edge(self, src_kind: str, src_key: str, dst_kind: str, dst_key: str, edge: str, props: dict[str, Any] | None = None) -> None:
        try:
            self._post(
                "/edges",
                {
                    "namespace": self.namespace,
                    "src": {"kind": src_kind, "key": src_key},
                    "dst": {"kind": dst_kind, "key": dst_key},
                    "edge": edge,
                    "props": props or {},
                },
            )
        except MemoryUnavailable:
            return

    def query_ticker_history(self, ticker: str, limit: int = 25) -> list[dict]:
        try:
            data = self._get(f"/query/{self.namespace}/ticker/{ticker}", {"limit": limit})
            return data.get("results", [])
        except MemoryUnavailable:
            return []

    def query_pattern_winrate(self, pattern: str) -> float | None:
        try:
            data = self._get(f"/stats/{self.namespace}/pattern/{pattern}")
            return data.get("winrate")
        except MemoryUnavailable:
            return None
