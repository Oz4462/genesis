"""Grok CLI adapter — a keyless ``LLMClient`` via the user's Grok subscription (OAuth).

Launches the ``grok`` CLI in single-prompt headless mode. System + user messages are
concatenated into one prompt (``-p`` / ``--prompt-file``).

IMPORTANT (verified live 2026-06-19): grok's ``--output-format json`` mode currently fails with
``Auth(AuthorizationRequired)`` and the call hangs in a re-auth retry loop — so this adapter does NOT
pass that flag. In plain mode grok prints the assistant text (including any requested JSON) cleanly on
stdout, with its connection/auth chatter on stderr, which ``default_cli_run`` captures separately and
``extract_cli_text`` ignores. The prompt still asks for JSON; the proposer parses it from stdout.

ARG_MAX (verified live 2026-07-13): GENESIS system prompts can exceed the OS argv limit when
passed via ``-p`` (``OSError: [Errno 7] Argument list too long``). Long prompts therefore use
``--prompt-file`` (temp file, deleted after the call).

Pair cross-model with a NON-xai generator (e.g. ``ClaudeCLI`` or ``OllamaLLM``);
``verification.cross_model.assert_different_families`` enforces the split (grok -> "xai").
"""

from __future__ import annotations

import os
import tempfile

from ..core.errors import LLMTransportError
from .base import LLMResponse
from ._cli import CliRunner, default_cli_run, extract_cli_text, resolve_binary

#: Prefer --prompt-file when system+user may blow OS ARG_MAX (live GENESIS prompts do).
_PROMPT_FILE_THRESHOLD = 4_000


class GrokCLI:
    """``LLMClient`` backed by the ``grok`` CLI (subscription OAuth, no key)."""

    def __init__(
        self,
        model: str = "grok-4.5",
        *,
        runner: CliRunner | None = None,
        timeout: float = 300.0,
        binary: str = "grok",
    ) -> None:
        if not model.strip():
            # An empty id defeats the cross-model audit (model_family raises on it);
            # fail at construction, not deep inside a run (mirrors OllamaLLM).
            raise ValueError("model id is empty; the cross-model audit needs a real id.")
        self.model = model
        if runner is not None:
            self._run = runner          # tests inject a fake; no real binary needed
            self._binary = binary
        else:
            # Prefer the real CLI binary over a PATH wrapper that injects --agent structured
            # (breaks headless -p / --prompt-file). Override: GENESIS_GROK_BINARY.
            self._binary = resolve_binary(binary, env_var="GENESIS_GROK_BINARY")

            async def _default(argv: list[str]) -> tuple[int, str, str]:
                return await default_cli_run(argv, timeout=timeout)

            self._run = _default

    async def complete(self, *, system: str, user: str) -> LLMResponse:
        prompt = f"{system}\n\n{user}" if system.strip() else user
        # NO --output-format json: grok's JSON mode auth-errors and hangs (see module docstring).
        # Plain mode prints the assistant text (incl. requested JSON) on stdout; chatter -> stderr.
        tmp_path: str | None = None
        if len(prompt) >= _PROMPT_FILE_THRESHOLD:
            fd, tmp_path = tempfile.mkstemp(prefix="genesis_grok_", suffix=".txt")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(prompt)
            except Exception:
                os.close(fd)
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                raise
            argv = [self._binary, "--prompt-file", tmp_path, "--model", self.model]
        else:
            argv = [self._binary, "-p", prompt, "--model", self.model]
        try:
            code, out, err = await self._run(argv)
        except Exception as exc:
            raise LLMTransportError(self.model, f"grok CLI transport failure: {exc}") from exc
        finally:
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        if code != 0:
            raise LLMTransportError(
                self.model, f"grok CLI exit {code}: {(err or out)[:200]}"
            )
        return LLMResponse(text=extract_cli_text(out, model=self.model), model=self.model)
