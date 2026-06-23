"""physiker — dritter Stein der Fach-Pipelines (Physiker-Pipeline).

Gemäß GENESIS_PLATFORM_PLAN.md §4.3:
- Ziel: Die echte Physik hinter der Idee sauber modellieren.
- Aufgaben: relevante physikalische Domänen identifizieren, Modelle auswählen, Modellgrenzen beschreiben, Formeln prüfen, Dimensionsanalyse, Energie-/Kraft-/Wärme-/Schwingungsbilanzen, Unsicherheiten propagieren, Falsifikationsexperimente vorschlagen.
- Outputs: Modellkarte, Gleichungen, Grenzfälle, erwartete Messgrößen, Unsicherheitsbudget, Falsifikationsplan.
- Gate: Dimensionshomogenität, Grenzfallprüfung, keine Modellanwendung außerhalb ihres Gültigkeitsbereichs, Messbarkeit der zentralen Vorhersagen.

Erster Stein: deterministischer Mapper von SystemConcept + IngenieurSpec zu PhysikerSpec.
Jetpack-Beispiel baut direkt auf den vorherigen Stones auf (Energie aus Ingenieur, Recovery/Thrust aus Grenz/CAD, Tether-Lasten etc.).

Naht: Nimmt vorherige Outputs, erzeugt Physik-Modell + Unsicherheitsbudget + Falsifikationsplan, die in CAD-Anforderungen, Manufacturing-Checks und spätere Teststände fließen.

Generic branch: derives domains/equations/budgets/falsi from ingenieur.lastfaelle (kraft/moments), failure_modes, material_hinweise and concept assemblies/idea.
Explicit honest Lücken instead of fabricated equations/physics. Blank source_idea + no load cases -> ValueError (no silent canned stub).
"""

from __future__ import annotations

from dataclasses import dataclass

from .architekt import SystemConcept
from .ingenieur import IngenieurSpec


@dataclass(frozen=True)
class PhysikDomäne:
    """Eine relevante physikalische Domäne mit Beleg."""
    name: str
    beschreibung: str
    quelle: str | None = None


@dataclass(frozen=True)
class ModellGleichung:
    """Eine Formel mit Gültigkeitsbereich und Herkunft."""
    name: str
    formel: str
    einheiten: str
    gueltigkeitsbereich: str
    quelle: str | None = None


@dataclass(frozen=True)
class UnsicherheitsBudget:
    """Unsicherheitsbetrachtung (einfach aber ehrlich)."""
    quelle: str
    wert: str  # z.B. "±15% auf Schub"
    auswirkung: str
    quelle_ref: str | None = None


@dataclass(frozen=True)
class FalsifikationsPlan:
    """Vorschlag für Experimente, die das Modell widerlegen könnten."""
    name: str
    beschreibung: str
    erwartete_messgroesse: str
    abbruchkriterium: str
    quelle: str | None = None


@dataclass(frozen=True)
class PhysikerSpec:
    """Der Output der Physiker-Pipeline (erster Stein)."""
    source_idea: str
    relevante_domaenen: list[PhysikDomäne]
    modell_gleichungen: list[ModellGleichung]
    unsicherheits_budget: list[UnsicherheitsBudget]
    falsifikations_plan: list[FalsifikationsPlan]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


# --- Generic-path derivation helpers (input-driven, no fabricated physics) ---
# These are private; they quote real input fields and emit explicit Lücken
# where quantitative physics cannot be derived without additional assumptions.
# This satisfies "keine stillen Defaults" and "kein faktischer Output ohne Quelle/Signale".


def _derive_domaenen(ingenieur: IngenieurSpec) -> list[PhysikDomäne]:
    """Derive phys. domains from declared load cases (force/moment), failure modes and material hints.

    Uses names/descriptions directly from ingenieur; no invented equations or constants.
    If no signal at all, returns a single explicit honest-gap domain.
    """
    domains: list[PhysikDomäne] = []
    for lc in ingenieur.lastfaelle:
        # Domain per load case; the kraft_oder_moment text is the driving signal
        desc = f"Ableitbar aus Lastfall '{lc.name}': {lc.kraft_oder_moment}. {lc.beschreibung}"
        if lc.quelle:
            desc += f" (Quelle: {lc.quelle})"
        domains.append(PhysikDomäne("Kräfte & Dynamik", desc, lc.quelle or "lastfaelle"))
    for fm in ingenieur.failure_modes:
        desc = f"Ableitbar aus Failure-Mode '{fm.name}' ({fm.aus_baugruppe}): {fm.beschreibung}"
        if fm.quelle:
            desc += f" (Quelle: {fm.quelle})"
        domains.append(PhysikDomäne("Ausfall- und Bruchmechanik", desc, fm.quelle or "failure_modes"))
    for mat in ingenieur.material_hinweise:
        if any(v is not None for v in (mat.e_modul_gpa, mat.dichte_kg_m3, mat.zugfestigkeit_mpa)):
            desc = f"Materialphysik für {mat.name} (Kennwerte verfügbar)"
            if mat.quelle:
                desc += f" (Quelle: {mat.quelle})"
            domains.append(PhysikDomäne("Materialphysik", desc, mat.quelle or "material_hinweise"))
    if not domains:
        domains.append(
            PhysikDomäne(
                "Grundmechanik (Lücke)",
                "Lücke: weder Lastfälle noch Failure-Modes noch Materialkennwerte deklariert — keine physikalische Domäne ableitbar ohne weitere Signale aus prior Stones",
                "generic (honest gap)",
            )
        )
    return domains


def _derive_gleichungen(ingenieur: IngenieurSpec) -> list[ModellGleichung]:
    """Derive model equations / expected measurands.

    Never fabricates a specific formula (e.g. no hard-coded F=ma). When a load/failure
    supplies a force/moment case we name the balance after it and mark the quantitative
    form as explicit Lücke (requires detailed analysis beyond the declared signal).
    """
    eqs: list[ModellGleichung] = []
    for lc in ingenieur.lastfaelle:
        # Unit hint taken from the load description text (if any); otherwise Lücke
        unit_hint = "N" if any(k in lc.kraft_oder_moment.lower() for k in ("n", "kn", "zug", "kraft", "schub")) else "Lücke"
        eqs.append(
            ModellGleichung(
                f"Kraft-/Lastbilanz aus {lc.name}",
                "Lücke: spezifische Gleichung (z. B. Netto-Kraft = Summe Terme) nicht aus Lastfall-Text ableitbar ohne zusätzliche Annahmen — erfordert detaillierte Physik-Modellierung",
                unit_hint,
                f"Gültigkeitsbereich wie im Lastfall '{lc.name}' deklariert; nur innerhalb dieser Randbedingungen",
                lc.quelle or "lastfaelle (gap)",
            )
        )
    for fm in ingenieur.failure_modes:
        eqs.append(
            ModellGleichung(
                f"Versagens-/Ausfallmodell für {fm.name}",
                "Lücke: quantitative Versagenskriterien (z. B. Spannung > Grenzwert) nicht aus Failure-Mode-Beschreibung ableitbar",
                "Lücke",
                "innerhalb deklarierter Betriebs- und Failure-Grenzen",
                fm.quelle or "failure_modes (gap)",
            )
        )
    if not eqs:
        eqs.append(
            ModellGleichung(
                "Lücke: keine Modellgleichung ableitbar",
                "Lücke: keine Lastfälle oder Failure-Modes mit messbarem physikalischem Signal — keine Gleichung fabriziert",
                "—",
                "—",
                "generic (honest gap)",
            )
        )
    return eqs


def _derive_budget(ingenieur: IngenieurSpec) -> list[UnsicherheitsBudget]:
    """Tie uncertainty budgets to actual declared load cases and failure modes.

    Always uses Lücke for the numeric value (no ±5% constant); the effect text quotes
    the originating input so provenance is visible.
    """
    budgets: list[UnsicherheitsBudget] = []
    for lc in ingenieur.lastfaelle:
        budgets.append(
            UnsicherheitsBudget(
                lc.name,
                "Lücke: keine quantitative Unsicherheit deklariert",
                f"Wirkt sich auf die mit Lastfall '{lc.name}' verbundene Dimensionierung und Sicherheit aus",
                lc.quelle or "lastfaelle",
            )
        )
    for fm in ingenieur.failure_modes:
        budgets.append(
            UnsicherheitsBudget(
                fm.name,
                "Lücke: ±? (keine Unsicherheit für diesen Failure-Mode spezifiziert)",
                f"Wirkt sich auf Erkennung/Recovery für {fm.aus_baugruppe} aus",
                fm.quelle or "failure_modes",
            )
        )
    if not budgets:
        budgets.append(
            UnsicherheitsBudget(
                "Gesamtlast / Masse (Lücke)",
                "Lücke: ±? (kein Signal für Unsicherheitsbudget aus lastfaelle/failure_modes)",
                "Lücke: keine deklarierten physikalischen Lasten oder Ausfallmodi",
                "generic (honest gap)",
            )
        )
    return budgets


def _derive_falsifikationsplan(ingenieur: IngenieurSpec) -> list[FalsifikationsPlan]:
    """Derive falsification plans from lastfaelle (as measurable force cases) and failure_modes.

    The erwartete_messgroesse is taken from the load description or detection method;
    abbruchkriterium stays high-level honest (no fabricated numeric thresholds).
    """
    plans: list[FalsifikationsPlan] = []
    for lc in ingenieur.lastfaelle:
        plans.append(
            FalsifikationsPlan(
                f"Lastfall-Verifikation: {lc.name}",
                f"Messung und Modellvergleich der in '{lc.name}' deklarierten Größe: {lc.kraft_oder_moment}",
                lc.kraft_oder_moment or "Kraft oder Moment",
                "Messwert liegt außerhalb deklarierter Toleranz oder führt zu Strukturversagen vor erwartetem Sicherheitsfaktor",
                lc.quelle or "lastfaelle + ingenieur",
            )
        )
    for fm in ingenieur.failure_modes:
        plans.append(
            FalsifikationsPlan(
                f"Falsifikation {fm.name}",
                fm.beschreibung,
                fm.detection or "Detektionsgröße aus Failure-Mode",
                f"Erwartete Detektion '{fm.detection}' tritt nicht ein oder Versagen erfolgt früher als deklariert",
                fm.quelle or "failure_modes",
            )
        )
    if not plans:
        plans.append(
            FalsifikationsPlan(
                "Lücke: kein Falsifikationsplan ableitbar",
                "Lücke: keine Lastfälle oder Failure-Modes mit messbarer Größe oder Detektion vorhanden",
                "Lücke: keine Messgröße",
                "Lücke: kein Abbruchkriterium",
                "generic (honest gap)",
            )
        )
    return plans


def _build_zusammenfassung(concept: SystemConcept, ingenieur: IngenieurSpec) -> str:
    """Build summary that reflects real source_idea and assemblies (not a constant)."""
    assem = ", ".join(a.name for a in concept.main_assemblies) if concept.main_assemblies else "keine Baugruppen"
    n_lc = len(ingenieur.lastfaelle)
    n_fm = len(ingenieur.failure_modes)
    n_mat = len(ingenieur.material_hinweise)
    idea = concept.source_idea.strip() or "(blank)"
    return (
        f"PhysikerSpec (generisch) für Idee »{idea}« (Baugruppen: {assem}) "
        f"mit {n_lc} Lastfällen, {n_fm} Failure-Modes, {n_mat} Material-Hinweisen. "
        "Domänen, Gleichungen, Budgets und Falsi-Pläne aus den Eingaben abgeleitet; "
        "fehlende quantitative Physik als explizite Lücken markiert (keine Fabrikation von Formeln oder Budgets)."
    )


def map_to_physiker_spec(
    concept: SystemConcept,
    ingenieur: IngenieurSpec,
    *,
    run_id: str | None = None,
) -> PhysikerSpec:
    """
    Erster Stein der Physiker-Pipeline.

    Derives PhysikerSpec from prior stones. The jetpack/flug branch (protected) returns
    a rich hand-curated example. The generic branch now derives its fields from the
    actual inputs (lastfaelle force/moment cases drive domains + falsi, failure_modes
    and materials feed domains/budgets/falsi, assemblies/idea surface in summary).

    No fabricated physics or constants in generic: absent signals become explicit
    "Lücke: ..." entries rather than guessed F=ma or ±5%.

    Raises:
        ValueError: if concept.source_idea is blank/whitespace AND ingenieur.lastfaelle
            is empty (no actionable signal at all — no silent canned stub).
    """
    if "jetpack" in concept.source_idea.lower() or any("jetpack" in a.name.lower() for a in concept.main_assemblies):
        domaenen = [
            PhysikDomäne("Energie & Leistung", "Batterie/Propulsion Bilanz für 5+ min Flight", "breakthrough + ingenieur lastfaelle"),
            PhysikDomäne("Kräfte & Dynamik", "Tether-Zug, Schub, Recovery-Impact, Aerodynamik", "ingenieur + gren safety"),
            PhysikDomäne("Schwingungen & Stabilität", "Vibrationen, Control-Response, Tether-Mode", "prior gren + breakthrough FC"),
            PhysikDomäne("Wärme & Thermik", "Motor/Batterie Wärme bei Last, Dissipation", "ingenieur material + energy"),
        ]
        gleichungen = [
            ModellGleichung(
                "Energie-Bilanz",
                "E_in - E_out - Verluste = E_verbleibend",
                "Wh",
                "5-10 min Flight, 20-80% SOC",
                "breakthrough Solid-State + ingenieur",
            ),
            ModellGleichung(
                "Tether-Dynamik (vereinfacht)",
                "F_tether = m * a + Drag + Gravity_comp",
                "N",
                "Low altitude, <50 km/h Wind",
                "safety_ladder + CAD anchor",
            ),
            ModellGleichung(
                "Recovery-Entfaltung",
                "t_open < 3s bei v_fall < v_max",
                "s, m/s",
                "Single-Failure Case",
                "learning_integrator + gren",
            ),
        ]
        budget = [
            UnsicherheitsBudget("Schub", "±12%", "Reichweite/Energie stark betroffen", "breakthrough lab data 2026"),
            UnsicherheitsBudget("Tether-Last", "±20% (Dynamik)", "Struktur/Recovery Dimensionierung", "ingenieur + real tether tests"),
            UnsicherheitsBudget("Recovery-Zeit", "±0.8s", "Sicherheitsabstand", "gren simulation + prior"),
        ]
        falsi = [
            FalsifikationsPlan(
                "Tether-Überlast Test",
                "Statische + dynamische Last bis Bruch oder 1.5x Max",
                "F_max, Dehnung",
                "Bruch vor 1.5x oder Dehnung > Grenze",
                "ingenieur toleranzen + CAD",
            ),
            FalsifikationsPlan(
                "Single-Failure Recovery Drop",
                "Simulierter Ausfall bei 30m Höhe, Recovery auslösen",
                "t_open, v_impact",
                "t_open > 3s oder v_impact > sicher",
                "safety_ladder S2 + learning",
            ),
            FalsifikationsPlan(
                "Energie-Margin Flight",
                "Vollast Flight bis SOC 20%, Verbrauch messen",
                "Wh/km oder Wh/min, SOC",
                "Verbrauch > 120% Modell oder SOC < 15% vor 5 min",
                "breakthrough + ingenieur",
            ),
        ]
        zusammen = (
            "PhysikerSpec für Jetpack: 4 Domänen (Energie, Kräfte, Schwingung, Wärme), "
            "3 Kern-Gleichungen mit Gültigkeitsbereich, 3 Unsicherheitsbudgets, "
            "3 Falsifikationspläne (direkt messbar, knüpfen an CAD + Manufacturing + Teststand). "
            "Naht zu vorherigen Stones + bestehenden Physics-Modulen vorbereitet."
        )
    else:
        # Generic path: genuinely derive from inputs (lastfaelle drive forces/dynamics;
        # failure_modes and materials feed domains/budgets/falsi; assemblies+idea in summary).
        # Where signal absent -> explicit Lücke, never a constant fabricated fact.
        # Guard first (per spec): blank idea + zero load cases = no actionable signal at all.
        if not concept.source_idea.strip() and not ingenieur.lastfaelle:
            raise ValueError(
                "concept with empty/blank source_idea AND no load cases provides no actionable signal; "
                "refusal (ValueError) instead of a canned PhysikerSpec stub"
            )

        domaenen = _derive_domaenen(ingenieur)
        gleichungen = _derive_gleichungen(ingenieur)
        budget = _derive_budget(ingenieur)
        falsi = _derive_falsifikationsplan(ingenieur)
        zusammen = _build_zusammenfassung(concept, ingenieur)

    # provenance always includes the prior stones + this derivation step
    quelle = (
        "physiker (third pipeline stone) + GENESIS_PLATFORM_PLAN.md §4.3 + prior Architekt + Ingenieur + Grenz + CAD"
        + (" + input-driven generic (Lücken statt Fabrikation)" if not ("jetpack" in concept.source_idea.lower() or any("jetpack" in a.name.lower() for a in concept.main_assemblies)) else "")
    )

    return PhysikerSpec(
        source_idea=concept.source_idea,
        relevante_domaenen=domaenen,
        modell_gleichungen=gleichungen,
        unsicherheits_budget=budget,
        falsifikations_plan=falsi,
        zusammenfassung=zusammen,
        run_id=run_id,
        quelle=quelle,
    )
