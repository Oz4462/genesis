"""verify_cli_launch — prove the hardened Windows CLI adapter launches a real .cmd shim and passes
arguments through cmd.exe intact, WITHOUT any network.

Why this exists: the unit suite pins the quoting MATH offline (tests/test_llm_cli_adapters.py), but
the real subprocess launch can only be confirmed against the actual OS + the actual npm claude.CMD.
This script does exactly that, with no network and no OAuth, so it is safe to run anywhere the CLIs
are installed:

  1. trivial spawn capability  (python -> python: does subprocess work here at all?)
  2. quoting fidelity end-to-end: build a temp .cmd shim that forwards its args (%*, the npm pattern)
     to a python arg-printer, drive it through the adapter's REAL default_cli_run, and assert every
     hazard argument (caret, quote, &, |, <, >, spaces, parens) round-trips byte-for-byte.
  3. real launch: shell out to the actual `claude` CLI via _launch_spec with `--version` (exits
     without network) — proof that the genuine claude.CMD launches through the hardened command line.

Run in a native terminal:  python scripts/verify_cli_launch.py
Exit 0 = all confirmations passed. Non-zero = a real launch/quoting problem (printed).
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.llm._cli import default_cli_run, _launch_spec  # noqa: E402

# ASCII cmd-metacharacter hazards — the exact class the two-layer quoting must protect. A umlaut is
# tested separately because non-ASCII through a cmd argv is a code-page concern, orthogonal to quoting.
HAZARDS = ["a^3", 'json{"k":1}', "a&b|c", "lt<gt>", "two words", "(paren)", "tab\tsep"]
UMLAUT = "umlaut-ä-ö-ü"


def _probe(label: str, argv: list[str] | str) -> tuple[bool, str]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=25)
    except subprocess.TimeoutExpired:
        return False, f"[{label}] TIMEOUT (no return in 25s)"
    except Exception as exc:  # noqa: BLE001 — report any spawn failure verbatim
        return False, f"[{label}] {type(exc).__name__}: {exc}"
    return r.returncode == 0, f"[{label}] rc={r.returncode} out={r.stdout.strip()[:60]!r}"


def main() -> int:
    print("platform:", sys.platform)
    if sys.platform != "win32":
        print("NOTE: not win32 — the .cmd route is a no-op here; run this on native Windows.")

    ok_all = True

    # 1) trivial spawn capability (the path previously suspected to hang)
    ok, msg = _probe("trivial-py", [sys.executable, "-c", "print('spawn-works')"])
    print(msg)
    ok_all &= ok
    if not ok:
        print(">> spawn itself is blocked here; the launch cannot be confirmed in this environment.")
        return 2

    # 2) quoting fidelity end-to-end through a real .cmd shim
    tmp = Path(tempfile.mkdtemp(prefix="gen_verify_"))
    printer = tmp / "argprint.py"
    # binary stdout, NUL-joined: faithful argv with no newline/CR translation surprises
    printer.write_text(
        "import sys\nsys.stdout.buffer.write('\\x00'.join(sys.argv[1:]).encode('utf-8'))\n",
        encoding="utf-8",
    )
    shim = tmp / "echo.cmd"
    shim.write_text('@python "%~dp0argprint.py" %*\r\n', encoding="ascii")

    cases = HAZARDS + [UMLAUT]
    argv = [str(shim), *cases]
    print("\nlaunch_spec ->", _launch_spec(argv))
    code, out, err = asyncio.run(default_cli_run(argv, timeout=25))
    got = out.split("\x00") if out else []
    print(f"[adapter-.cmd] rc={code} got {len(got)} args (sent {len(cases)})")
    if err.strip():
        print(f"   stderr: {err.strip()[:160]}")
    quoting_ok = True
    for sent, recv in zip(cases, got + [""] * len(cases)):
        match = sent == recv
        if sent == UMLAUT and not match:
            print(f"   ~~ sent={sent!r} got={recv!r}  (non-ASCII via cmd argv = code-page caveat, not quoting)")
            continue
        print(f"   {'OK ' if match else 'XX '} sent={sent!r} got={recv!r}")
        quoting_ok &= match
    if len(got) != len(cases):
        print(f"   !! arg COUNT mismatch: a metacharacter split an argument")
        quoting_ok = False
    ok_all &= quoting_ok

    # 3) the REAL claude CLI launches through the hardened command line (no network: --version)
    claude = shutil.which("claude")
    if claude:
        print()
        ok, msg = _probe("claude--version", _launch_spec([claude, "--version"]))
        print(f"{msg}   (resolved: {claude})")
        ok_all &= ok
    else:
        print("\n[claude--version] SKIP: claude not on PATH")

    shutil.rmtree(tmp, ignore_errors=True)
    print("\n=== RESULT:", "ALL CONFIRMED" if ok_all else "PROBLEM FOUND", "===")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
