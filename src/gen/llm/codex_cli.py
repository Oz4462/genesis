"""Codex CLI adapter — non-interactive Codex via the installed codex subscription/tool.

Uses `codex exec --skip-git-repo-check --model <m> --output-last-message <tmp> "prompt"`
to get clean last-message output. Codex is more agentic/repo-oriented than claude/grok,
so we force skip-git and ephemeral-friendly flags where sensible.

Pair with a different family for cross-model verification.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from ..core.errors import LLMTransportError
from .base import LLMResponse
from ._cli import CliRunner, default_cli_run, extract_cli_text, resolve_binary


class CodexCLI:
    """``LLMClient`` backed by the ``codex`` CLI (exec mode, no key)."""

    def __init__(
        self,
        model: str = "gpt-5.5",  # or whatever codex defaults to in the env
        *,
        runner: CliRunner | None = None,
        timeout: float = 300.0,
        binary: str = "codex",
    ) -> None:
        if not model.strip():
            raise ValueError("model id is empty; the cross-model audit needs a real id.")
        self.model = model
        if runner is not None:
            self._run = runner
            self._binary = binary
        else:
            self._binary = resolve_binary(binary)

            async def _default(argv: list[str]) -> tuple[int, str, str]:
                return await default_cli_run(argv, timeout=timeout)

            self._run = _default

    async def complete(self, *, system: str, user: str) -> LLMResponse:
        # Codex exec takes the prompt as initial instructions.
        # We combine system + user for best compatibility.
        prompt = f"System: {system}\n\nUser: {user}" if system.strip() else user

        # Use a unique temp file for clean last message.
        tmp_path = f"/tmp/codex-last-{uuid.uuid4().hex}.txt"
        try:
            argv = [
                self._binary,
                "exec",
                "--skip-git-repo-check",
                "--model", self.model,
                "--output-last-message", tmp_path,
                prompt,
            ]
            code, out, err = await self._run(argv)
        except Exception as exc:
            raise LLMTransportError(self.model, f"codex CLI transport failure: {exc}") from exc
        finally:
            # best effort cleanup
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass

        if code != 0:
            raise LLMTransportError(
                self.model, f"codex CLI exit {code}: {(err or out)[:300]}"
            )

        # Prefer the output file if it was written with content.
        text = ""
        try:
            if os.path.exists(tmp_path):
                with open(tmp_path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read().strip()
        except Exception:
            pass

        if not text:
            # Fallback to parsing stdout (last non-metadata block)
            text = extract_cli_text(out, model=self.model)

        return LLMResponse(text=text, model=self.model)
