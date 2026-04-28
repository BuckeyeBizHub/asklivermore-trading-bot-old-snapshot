"""
core.adapters.peers_adapter
===========================
Adapter for so-ainsight/claude-peers. Lets sibling agent runs exchange short
advisory messages on a shared topic. Used by PeerCoordinatorAgent.

If claude-peers isn't installed, returns an empty list (no peer advice).
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

from core.config import settings
from core.logging import get_logger
from core.state import PeerMessage

log = get_logger(__name__)


class PeersAdapter:
    def __init__(self) -> None:
        self._peers = self._try_load()

    def _try_load(self):
        path = settings.external_path_claude_peers
        if not Path(path).exists():
            log.warning("claude_peers.not_installed", path=str(path))
            return None
        pkg = Path(path) / "src"
        if str(pkg) not in sys.path:
            sys.path.insert(0, str(pkg))
        try:
            spec = importlib.util.find_spec("claude_peers")
            if spec is None:
                return None
            return importlib.import_module("claude_peers")
        except Exception as e:
            log.warning("claude_peers.import_failed", error=str(e))
            return None

    def publish(self, content: str, confidence: float = 0.5) -> None:
        if self._peers is None:
            return
        try:
            self._peers.publish(  # type: ignore[attr-defined]
                topic=settings.peer_topic,
                peer_id=settings.peer_id,
                payload={"content": content, "confidence": confidence},
            )
        except Exception as e:
            log.warning("claude_peers.publish_failed", error=str(e))

    def fetch_recent(self, max_age_s: int = 60) -> list[PeerMessage]:
        if self._peers is None:
            return []
        try:
            raw = self._peers.fetch(  # type: ignore[attr-defined]
                topic=settings.peer_topic,
                exclude_peer_id=settings.peer_id,
                max_age_s=max_age_s,
            )
            return [
                PeerMessage(
                    from_peer=str(m.get("peer_id", "?")),
                    content=str(m.get("payload", {}).get("content", "")),
                    confidence=float(m.get("payload", {}).get("confidence", 0.5)),
                )
                for m in raw
            ]
        except Exception as e:
            log.warning("claude_peers.fetch_failed", error=str(e))
            return []
