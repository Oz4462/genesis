"""Render a complete γ Specification as a Markdown build manual.

This is the human deliverable: a single, shareable document (which a tool can turn
into PDF/HTML) carrying every part of the spec — quantities with provenance,
mechanical and electronics BOMs with claim-backed sourcing and a cost roll-up,
geometry, numbered build steps with tools/torque/checks, constraints, decisions,
site requirements, the deterministic δ validation (envelope/volume/mass), and a
Sources appendix listing the ledger claims it rests on.

Deterministic and offline. Every factual value shown here is a VERIFIED claim or a
declared/recomputed quantity — the document never asserts anything the gates did
not allow (an honest gap is printed as a gap, not hidden).
"""

from __future__ import annotations

from ..completeness import completeness_warnings
from ..core.state import BomDomain, Specification, ValueOrigin
from ..costing import bom_cost, format_cost
from ..verification.gates import gate_delta, geometry_envelope
from ..verification.geometry import GeometryError, geometry_length_unit, mass_of, volume_of


def _origin(q) -> str:
    if q.origin is ValueOrigin.GROUNDED:
        return f"belegt durch {', '.join(q.grounding)}"
    if q.origin is ValueOrigin.DERIVED:
        return f"berechnet = `{q.derivation.formula}`" if q.derivation else "berechnet"
    return f"Entscheidung — {q.rationale}"


def _geometry_md(node, depth: int) -> list[str]:
    pad = "  " * depth
    params = ", ".join(f"{k}={v}" for k, v in sorted(node.params.items()))
    head = f"{pad}- `{node.kind}`" + (f" ({params})" if params else "")
    out = [head]
    for child in node.children:
        out.extend(_geometry_md(child, depth + 1))
    return out


def specification_to_markdown(spec: Specification) -> str:
    q = {x.id: x for x in spec.quantities}
    md: list[str] = []
    a = md.append

    a(f"# Bauanleitung: {spec.idea}")
    a("")
    a(f"- Lauf: `{spec.run_id}`")
    if spec.approach_id:
        a(f"- Lösungsansatz: `{spec.approach_id}`")
    a("")
    a("> Jeder Wert in diesem Dokument ist ein verifizierter Beleg oder eine "
      "deklarierte/nachgerechnete Größe. Nichts ist erfunden; ehrliche Lücken "
      "stehen als Lücken da.")
    a("")

    if spec.quantities:
        a("## Größen")
        a("")
        a("| id | Name | Wert | Einheit | Herkunft |")
        a("|----|------|------|---------|----------|")
        for x in spec.quantities:
            a(f"| `{x.id}` | {x.name} | {x.value:g} | {x.unit} | {_origin(x)} |")
        a("")

    if spec.components:
        a("## Bauteile (parametrische CSG-Geometrie)")
        a("")
        for comp in spec.components:
            a(f"### {comp.name} (`{comp.id}`)")
            if comp.material_density:
                a(f"- Materialdichte: `{comp.material_density}`")
            if comp.geometry is not None:
                a("")
                md.extend(_geometry_md(comp.geometry, 0))
            a("")

    if spec.bom:
        mech = [b for b in spec.bom if b.domain is BomDomain.MECHANICAL]
        elec = [b for b in spec.bom if b.domain is BomDomain.ELECTRONIC]

        def _bom_table(title, items):
            a(f"## {title}")
            a("")
            a("| Anzahl | Teil | Rolle | Bezug | Stückpreis |")
            a("|--------|------|-------|-------|-----------|")
            for it in items:
                src = "—"
                price = "—"
                if it.sourcing is not None:
                    src = f"{it.sourcing.supplier} #{it.sourcing.part_number}"
                    pid = it.sourcing.price_quantity_id
                    if pid and pid in q:
                        price = f"{q[pid].value:g} {q[pid].unit}"
                a(f"| {it.count} | {it.name} | {it.role.value} | {src} | {price} |")
            a("")

        _bom_table("Stückliste (Mechanik)", mech or [])
        if elec:
            _bom_table("Stückliste (Elektronik)", elec)
        a(f"**Geschätzte Kosten:** {format_cost(bom_cost(spec))}")
        a("")

    if spec.steps:
        a("## Bauschritte")
        a("")
        for s in sorted(spec.steps, key=lambda s: s.index):
            a(f"{s.index}. {s.action}")
            if s.tool:
                a(f"   - Werkzeug: {s.tool}")
            if s.uses:
                a(f"   - verwendet: {', '.join(s.uses)}")
            if s.torque_quantity_id and s.torque_quantity_id in q:
                tq = q[s.torque_quantity_id]
                a(f"   - Anzugsmoment: {tq.value:g} {tq.unit}")
            a(f"   - Prüfung: {s.check}")
        a("")

    if spec.constraints:
        a("## Geprüfte Anforderungen")
        a("")
        for k in spec.constraints:
            a(f"- `{k.left} {k.kind} {k.right}` — {k.reason}")
        a("")

    if spec.decisions:
        a("## Entscheidungsblatt")
        a("")
        a("> Entscheidungen, keine Fakten — ratifizieren oder ändern.")
        a("")
        for d in spec.decisions:
            a(f"- **{d.title}:** {d.choice} — {d.rationale}")
        a("")

    if spec.site is not None:
        a("## Ort & Umgebung")
        a("")
        if spec.site.available_space is not None:
            dims = [f"{q[qid].value:g} {q[qid].unit}" for qid in spec.site.available_space if qid in q]
            if dims:
                a(f"- verfügbarer Platz: {' × '.join(dims)}")
        for d in spec.site.requirements:
            a(f"- **{d.title}:** {d.choice} — {d.rationale}")
        a("")

    if spec.components:
        a("## Geometrische Validierung (δ — nur Geometrie, kein Physik-Urteil)")
        a("")
        state = _spec_state(spec)
        env = geometry_envelope(state)
        for cid, (ex, ey, ez) in env.items():
            a(f"- `{cid}` Hüllmaß: {ex:g} × {ey:g} × {ez:g}")
            comp = next((c for c in spec.components if c.id == cid), None)
            if comp is not None and comp.geometry is not None:
                a(f"  - {_volume_md(comp, q)}")
                ml = _mass_md(comp, q)
                if ml:
                    a(f"  - {ml}")
        result = gate_delta(state)
        verdict = ("keine beweisbar defekte Geometrie (PASS — notwendig, nicht hinreichend)"
                   if result.passed else f"FAIL: {[f.code for f in result.failures]}")
        a(f"- Status: {verdict}")
        a("")

    warnings = completeness_warnings(spec)
    if warnings:
        a("## Vollständigkeits-Warnungen")
        a("")
        a("> Die Spezifikation ist konsistent, aber vermutlich unterspezifiziert:")
        a("")
        for w in warnings:
            a(f"- {w}")
        a("")

    if spec.gaps:
        a("## Lücken (ausdrücklich NICHT behauptet)")
        a("")
        for gap in spec.gaps:
            a(f"- {gap}")
        a("")

    if spec.claim_ids_used:
        a("## Quellen (Ledger-Belege, auf denen diese Anleitung beruht)")
        a("")
        for cid in spec.claim_ids_used:
            a(f"- `{cid}`")
        a("")

    return "\n".join(md)


def _volume_md(comp, q) -> str:
    try:
        vol = volume_of(comp.geometry, q)
    except GeometryError:
        return "Volumen: nicht berechenbar"
    unit = geometry_length_unit(comp.geometry, q)
    us = f" {unit}³" if unit else ""
    if vol.exact:
        return f"Volumen: {vol.value:g}{us} (exakt)"
    return f"Volumen: ≤ {vol.value:g}{us} (obere Schranke — {vol.note})"


def _mass_md(comp, q) -> str | None:
    if comp.material_density is None:
        return None
    m = mass_of(comp, q)
    if m.value is None:
        return f"Masse: nicht berechenbar — {m.note}"
    qualifier = "exakt" if m.exact else f"obere Schranke — {m.note}"
    return f"Masse: {m.value:g} {m.unit} ({qualifier})"


def _spec_state(spec: Specification):
    from ..core.state import Question, RunState
    st = RunState(question=Question(raw=spec.idea, run_id=spec.run_id))
    st.specification = spec
    return st
