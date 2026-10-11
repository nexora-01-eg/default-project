"""ExecutionAdapter contract shared by all provider adapters."""
from __future__ import annotations


class AdapterError(RuntimeError):
    pass


class ToolUnavailable(AdapterError):
    def __init__(self, provider: str, reason: str):
        super().__init__(f"{provider}: TOOL_UNAVAILABLE ({reason})")
        self.provider = provider
        self.reason = reason


class ExecutionAdapter:
    provider_id: str = "base"
    capabilities: tuple = ()

    def available(self) -> tuple[bool, str]:
        raise NotImplementedError

    def _require(self) -> None:
        ok, reason = self.available()
        if not ok:
            raise ToolUnavailable(self.provider_id, reason)

    def run(self, contract: dict) -> dict:
        raise NotImplementedError

    @staticmethod
    def artifact(kind: str, path: str, provider: str, **extra) -> dict:
        out = {"kind": kind, "path": str(path), "provider": provider}
        out.update(extra)
        return out
