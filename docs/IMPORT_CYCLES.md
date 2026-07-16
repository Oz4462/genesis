# Import cycles (audit F1, 2026-07-16)

## Known 2-cycles

| Pair | Notes |
|------|--------|
| verification ↔ coverage | `gate_delta_plus_coverage` re-exported from verification (now **lazy**) |
| verification ↔ seams | `gate_epsilon` (lazy) |
| verification ↔ uncertainty | residual |
| cad ↔ pipelines | assembly/realization fragments |
| cad ↔ export | drawing/stl bridges |
| grenzverschiebung ↔ pipelines | LUMEN package |
| grenzverschiebung ↔ simulation | co-sim |
| lernmaschine ↔ pipelines | package cycle |
| pipelines ↔ wissensbasis | store |

## Mitigation

- **2026-07-16:** `verification/__init__.py` no longer eagerly imports coverage/seams/memory_fabric/omega; use `__getattr__` for those four gates.
- Callers should prefer `from gen.seams import gate_epsilon` (etc.) over `from gen.verification import gate_epsilon` for clarity.
- Long-term: move pure gate interfaces into `gen.core` to eliminate package-level cycles.

## How to check

```bash
# Example: detect import edges (manual)
python -c "import gen.verification; import gen.coverage; print('ok')"
```
