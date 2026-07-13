"""Claude Code CLI adapter — a keyless ``LLMClient`` via the user's Claude subscription (OAuth).

Launches the ``claude`` CLI in headless print mode
(``claude -p <user> --append-system-prompt <system> --model <m> --output-format json``),
which authenticates through the installed Claude (Max) subscription — no API key, no
per-token billing. Unlike ``grok -p``, the ``claude`` CLI keeps the system prompt separate
via ``--append-system-prompt``.

Pair cross-model with a NON-claude verifier (e.g. ``GrokCLI`` or ``OllamaLLM``);
``verification.cross_model.assert_different_families`` enforces the split (claude -> "claude").

Note on determinism: the subscription CLI path does not expose ``temperature``, so it is NOT
bit-reproducible like the local ``OllamaLLM`` (temp 0). Use the local path when reproducibility
(A5) is required; use this path for the live Claude-Max generator/verifier.
"""

from __future__ import annotations

from ..core.errors import LLMTransportError
from .base import LLMResponse
from ._cli import CliRunner, default_cli_run, extract_cli_text, resolve_binary, resolve_llm_timeout


class ClaudeCLI:
    """``LLMClient`` backed by the ``claude`` CLI (subscription OAuth, no key)."""

    def __init__(
        self,
        model: str = "claude-opus-4-8",
        *,
        runner: CliRunner | None = None,
        timeout: float | None = None,
        binary: str = "claude",
    ) -> None:
        if not model.strip():
            raise ValueError("model id is empty; the cross-model audit needs a real id.")
        self.model = model
        timeout = resolve_llm_timeout(timeout)
        if runner is not None:
            self._run = runner          # tests inject a fake; no real binary needed
            self._binary = binary
        else:
            self._binary = resolve_binary(binary)

            async def _default(argv: list[str]) -> tuple[int, str, str]:
                return await default_cli_run(argv, timeout=timeout)

            self._run = _default

    async def complete(self, *, system: str, user: str) -> LLMResponse:
        argv = [self._binary, "-p", user, "--model", self.model, "--output-format", "json"]
        if system.strip():
            argv += ["--append-system-prompt", system]
        try:
            code, out, err = await self._run(argv)
        except Exception as exc:
            raise LLMTransportError(self.model, f"claude CLI transport failure: {exc}") from exc
        if code != 0:
            raise LLMTransportError(
                self.model, f"claude CLI exit {code}: {(err or out)[:200]}"
            )
        return LLMResponse(text=extract_cli_text(out, model=self.model), model=self.model)
