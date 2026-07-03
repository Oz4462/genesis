"""PoV-4 harness — does VERIDEX/trust-core add a manipulation-proof audit trail
+ model-drift monitoring that GENESIS lacks?

GENESIS today has NO signing dependency (no cryptography/pynacl in pyproject, no
receipts module) and NO drift detector. VERIDEX's audit layer is built on
trust-core primitives (DSSE/Ed25519 receipts + CCDD drift), so this harness proves
the underlying capability with those primitives, offline, deterministically.

Proves with numbers:
  1. SIGN/VERIFY  — a Genesis-run audit record signs to a DSSE envelope and verifies
     with the issuer public key.
  2. TAMPER       — flipping one payload byte makes verification fail (tamper-evident).
  3. WRONG KEY    — verification under a different public key fails (no forgery).
  4. DRIFT        — CCDD streaming detector flags a generator-output shift, stays quiet
     on no-shift (model-drift monitoring for the live operator).

Deterministic: fixed Ed25519 seed (signatures are RFC 8032 deterministic), fixed
issued_at/receipt_id, seeded RNG. Writes runs/pov/pov4/report.json. Exit 0 iff PASS.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

_SCRIPT = Path(__file__).resolve()
_GENESIS_REPO = _SCRIPT.parents[2]
_DESKTOP = _GENESIS_REPO.parents[2]
_TRUSTCORE_SRC = _DESKTOP / "alle apps" / "trust-core" / "src"
if not _TRUSTCORE_SRC.exists():
    raise SystemExit(f"trust-core src missing: {_TRUSTCORE_SRC}")
sys.path.insert(0, str(_TRUSTCORE_SRC))

from nacl.signing import SigningKey, VerifyKey  # noqa: E402
from trust_core.receipts.receipts import (  # noqa: E402
    BoundRef,
    ModelRef,
    Receipt,
    ReceiptSigner,
    ReceiptVerifier,
    SignedEnvelope,
)
from trust_core.conformal.ccdd import calibrate, StreamingDetector  # noqa: E402

_FIXED_SEED = hashlib.sha256(b"genesis-pov4-issuer").digest()  # 32 bytes


def _genesis_audit_receipt() -> Receipt:
    """A receipt standing in for a GENESIS run's signed audit record."""
    ledger_digest = hashlib.sha256(
        b"run=pov4;claims=12;verified=10;refused=2;generator=qwen3.5:9b;verifier=gemma4:12b"
    ).hexdigest()
    return Receipt(
        tenant_id="genesis",
        request_id="pov4",
        model=ModelRef(provider="ollama", name="qwen3.5", version="9b"),
        capture_hash=ledger_digest,
        distill_model="gemma4:12b",
        retrieved_step_ids=["claim_3", "claim_7"],
        bound=BoundRef(tau=0.2, alpha=0.1, n_calibration=24),
        cost_saved_tokens=0,
        issued_at="2026-06-13T00:00:00+00:00",
        receipt_id="00000000-0000-0000-0000-0000000000p4",
    )


def prove_audit() -> dict:
    signer = ReceiptSigner(SigningKey(_FIXED_SEED), key_id="genesis-issuer-1")
    verifier = ReceiptVerifier.from_public_key_b64("genesis-issuer-1", signer.public_key_b64())

    receipt = _genesis_audit_receipt()
    env = signer.sign(receipt)

    # 1. valid verify
    verify_ok = False
    try:
        back = verifier.verify(env)
        verify_ok = back.capture_hash == receipt.capture_hash
    except Exception:
        verify_ok = False

    # 2. tamper: flip one byte inside the signed payload
    raw = bytearray(base64.b64decode(env.payload))
    raw[len(raw) // 2] ^= 0x01
    tampered = SignedEnvelope(
        payloadType=env.payloadType,
        payload=base64.b64encode(bytes(raw)).decode("ascii"),
        signatures=env.signatures,
    )
    tamper_detected = False
    try:
        verifier.verify(tampered)
    except Exception:
        tamper_detected = True

    # 3. wrong key
    other = SigningKey(hashlib.sha256(b"attacker").digest())
    wrong_verifier = ReceiptVerifier({"genesis-issuer-1": VerifyKey(bytes(other.verify_key))})
    wrong_key_rejected = False
    try:
        wrong_verifier.verify(env)
    except Exception:
        wrong_key_rejected = True

    return {
        "genesis_has_signing_today": False,
        "verify_ok": verify_ok,
        "tamper_detected": tamper_detected,
        "wrong_key_rejected": wrong_key_rejected,
        "pass": verify_ok and tamper_detected and wrong_key_rejected,
    }


def prove_drift_monitoring() -> dict:
    rng = np.random.default_rng(770077)
    d, n_cal, window = 8, 400, 100
    model = calibrate(rng.normal(0.0, 1.0, size=(n_cal, d)))

    def run(shift: float) -> bool:
        det = StreamingDetector(model, window_size=window, alpha_inner=0.05, alpha_outer=0.01)
        for i in range(300):
            det.observe(f"x{i}", rng.normal(shift, 1.0, size=d))
            if det.check_alert() is not None:
                return True
        return False

    no_shift = run(0.0)
    shifted = run(1.5)
    return {"no_shift_alerted": no_shift, "shift_alerted": shifted, "pass": (not no_shift) and shifted}


def main() -> int:
    audit = prove_audit()
    drift = prove_drift_monitoring()
    gate = audit["pass"] and drift["pass"]
    report = {
        "pov": "PoV-4 VERIDEX/trust-core governance",
        "run_id": "pov4",
        "audit": audit,
        "drift_monitoring": drift,
        "gate_pass": gate,
    }
    out = _GENESIS_REPO / "runs" / "pov" / "pov4"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=== PoV-4: VERIDEX/trust-core governance ===")
    print(
        f"A. audit  : verify={audit['verify_ok']} tamper_detected={audit['tamper_detected']} "
        f"wrong_key_rejected={audit['wrong_key_rejected']} -> {'PASS' if audit['pass'] else 'FAIL'}"
    )
    print(
        f"B. drift  : no_shift_alerted={drift['no_shift_alerted']} "
        f"shift_alerted={drift['shift_alerted']} -> {'PASS' if drift['pass'] else 'FAIL'}"
    )
    print(f"GATE: {'PASS' if gate else 'FAIL'}  (report: {out / 'report.json'})")
    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
