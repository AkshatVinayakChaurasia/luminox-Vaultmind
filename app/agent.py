from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path

from app import audit
from app.knowledge import KnowledgeBase
from app.runtime import snapshot as runtime_snapshot
from app.vision import inspect_image

STEPS = [
    ("understand", "Understand task"),
    ("retrieve", "Retrieve relevant maintenance manuals"),
    ("inspect", "Inspect uploaded image / report"),
    ("reason", "Reason over evidence"),
    ("calculate", "Run calculation / tool if required"),
    ("recommend", "Generate recommendation"),
    ("cite", "Cite evidence"),
    ("log", "Log entire operation"),
]

_THICK = re.compile(r"(\d+(?:\.\d+)?)\s*mm", re.I)

NONE = {"available": False, "label": "Evidence not available"}


def _nominal_for_context(text: str) -> tuple[float, float]:
    blob = text.lower()
    if "e-441" in blob or "exchanger" in blob or "hx" in blob:
        return 12.0, 8.5
    return 7.11, 4.80


def _cite(passage: dict | None) -> dict:
    if not passage:
        return dict(NONE)
    return {
        "available": True,
        "doc_id": passage.get("doc_id"),
        "title": passage.get("title"),
        "revision": passage.get("revision"),
        "page": passage.get("page"),
        "section": passage.get("section"),
        "citation": passage.get("citation"),
        "excerpt": passage.get("excerpt"),
    }


def _find(passages: list[dict], *needles: str) -> dict | None:
    lowered = [(p, (p.get("excerpt") or "").lower()) for p in passages]
    for p, blob in lowered:
        if all(n.lower() in blob for n in needles):
            return p
    for p, blob in lowered:
        if any(n.lower() in blob for n in needles):
            return p
    return passages[0] if passages else None


def run_inspection(payload: dict, kb: KnowledgeBase) -> dict:
    run_id = uuid.uuid4().hex[:12]
    request = (payload.get("request") or "").strip()
    image_path = payload.get("image_path")
    prior_report = (payload.get("prior_report") or "").strip()
    specs = (payload.get("specs") or "").strip()
    extra_docs = payload.get("extra_docs") or []
    runtime = runtime_snapshot()

    timeline: list[dict] = []

    def step(key: str, detail: str, data=None):
        item = {"step": key, "detail": detail, "data": data or {}, "at": datetime.now().strftime("%H:%M:%S")}
        timeline.append(item)
        return item

    task = request or "Perform a visual inspection of the uploaded asset and produce a grounded inspection note."
    asset_guess = "process piping"
    low = f"{task} {prior_report} {specs}".lower()
    if "pump" in low:
        asset_guess = "centrifugal pump"
    elif "exchanger" in low or "e-441" in low:
        asset_guess = "heat exchanger"
    step(
        "understand",
        f"Task classified as field inspection of {asset_guess}. Processing stays on this host.",
        {"task": task, "asset": asset_guess},
    )

    query = f"{task} {asset_guess} corrosion leak thickness grade inspection {specs}"
    retrieved = kb.search(query, extra=prior_report, k=4)
    step(
        "retrieve",
        f"Retrieved {len(retrieved)} internal passages from on-premise manuals.",
        {"hits": [{"citation": h["citation"], "title": h["title"], "section": h.get("section")} for h in retrieved]},
    )

    vision = None
    if image_path:
        try:
            vision = inspect_image(Path(image_path))
            step("inspect", "Image inspected locally. " + " ".join(vision["findings"]), vision)
        except Exception as exc:  # unreadable / unsupported file — never fail the whole run
            vision = None
            step(
                "inspect",
                "Uploaded file could not be read as an image "
                f"({type(exc).__name__}) — continuing from text and manuals only.",
                {"error": type(exc).__name__},
            )
    else:
        step("inspect", "No photograph supplied — reasoning from text and manuals only.", {})

    if prior_report:
        step("inspect", "Previous inspection report ingested as prior evidence.", {"chars": len(prior_report)})
    if extra_docs:
        step("inspect", f"Additional uploaded documents indexed: {len(extra_docs)}.", {"docs": extra_docs})

    grade = (vision or {}).get("visual_grade_hint") or "B"
    observations: list[str] = []
    if vision:
        observations.extend(vision["findings"])
    if prior_report:
        observations.append("Prior report text was compared against current visual cues.")
    if not vision:
        observations.append("No photograph; grading uses request text and retrieved procedures only.")
    if not retrieved:
        observations.append("Knowledge base returned no overlapping passages — recommendation is conservative.")
    step("reason", f"Observed condition mapped to AI assessment Grade {grade} against retrieved criteria.", {"grade": grade, "evidence": observations})

    blob = f"{task} {prior_report} {specs}"
    found = _THICK.findall(blob)
    remaining = float(found[0]) if found else None
    nominal, retire = _nominal_for_context(blob + " " + asset_guess)
    calc = {
        "nominal_mm": nominal,
        "retirement_mm": retire,
        "remaining_mm": remaining,
        "applied": remaining is not None,
        "source": "parsed from request / report / specs on this host",
    }
    if remaining is not None:
        calc["margin_mm"] = round(remaining - retire, 2)
        calc["status"] = "below_retirement" if remaining < retire else "above_retirement"
        if remaining >= retire and remaining <= 6.0 and retire == 4.80:
            calc["increased_frequency_band"] = True
        detail = (
            f"Remaining wall {remaining:.2f} mm vs retirement {retire:.2f} mm "
            f"(nominal {nominal:.2f} mm)."
        )
    else:
        detail = "No thickness reading in the request — skipped UT math; visual grading only."
    step("calculate", detail, calc)

    actions = {
        "A": "Record finding. Continue routine operator round. No special NDT hold.",
        "B": "Schedule NDT / thickness survey within 90 days. Re-photograph after cleaning loose dirt only.",
        "C": "Thickness survey within 30 days. Review remaining life. Do not disturb heavy scale on live hydrocarbon service.",
        "D": "Inspection hold. Restrict operations until Fitness-for-Service is complete.",
    }
    risks = {
        "A": "Continue routine surveillance. No special restriction from this run.",
        "B": "Re-photograph after cleaning loose dirt only. Confirm remaining wall on next survey.",
        "C": "Review remaining life. Schedule UT survey. Do not disturb heavy scale on live hydrocarbon service.",
        "D": "Operational restriction until Fitness-for-Service is complete.",
    }
    if calc.get("status") == "below_retirement":
        grade = "D"
    recommendation = actions.get(grade, actions["C"])
    risk_action = risks.get(grade, risks["C"])

    vis_conf = (vision or {}).get("confidence")
    if vis_conf is None:
        confidence = 0.58 if retrieved else 0.45
        confidence_kind = "heuristic prototype score (no image)"
    else:
        confidence = vis_conf
        confidence_kind = vision.get("confidence_kind") or "heuristic prototype score"
    if retrieved:
        confidence = min(0.92, round(confidence + 0.06, 2))

    obs_src = _find(retrieved, "visual classification", "grade c", "external corrosion")
    calc_src = _find(retrieved, "retirement", "acceptance criteria", "4.80")
    rec_src = _find(retrieved, "recommended actions", "ndt within")

    evidence_panel = {
        "observation": {
            "claim": observations[0] if observations else "No visual claim generated.",
            "evidence": _cite(obs_src if vision or retrieved else None),
        },
        "calculation": {
            "remaining_mm": remaining,
            "retirement_mm": retire,
            "nominal_mm": nominal,
            "applied": calc["applied"],
            "evidence": _cite(calc_src if calc["applied"] else None) if calc["applied"] else dict(NONE),
        },
        "recommendation": {
            "text": recommendation,
            "basis": [b for b in [
                f"Remaining wall {remaining:.2f} mm" if remaining is not None else None,
                f"Retirement threshold {retire:.2f} mm" if calc["applied"] else None,
                "Corrosion observation from local image analysis" if vision else None,
                "Previous inspection history on this host" if prior_report else None,
                "Maintenance criteria retrieved locally" if retrieved else None,
            ] if b],
            "evidence": _cite(rec_src),
        },
    }
    if not evidence_panel["observation"]["evidence"]["available"] and retrieved:
        evidence_panel["observation"]["evidence"] = _cite(retrieved[0])

    why = [b for b in [
        f"Remaining wall: {remaining:.2f} mm" if remaining is not None else None,
        f"Retirement threshold: {retire:.2f} mm",
        "External corrosion cues on the uploaded image" if vision else None,
        "Previous inspection text was supplied" if prior_report else None,
        "Relevant maintenance criteria retrieved locally" if retrieved else None,
    ] if b]

    step("recommend", recommendation, {"grade": grade})
    citations = [h["citation"] for h in retrieved]
    step("cite", "Citations bound to retrieved pages only — no web sources.", {"citations": citations, "passages": retrieved})

    clock = datetime.now().strftime("%H:%M:%S")
    image_name = Path(image_path).name if image_path else None
    audit_chain = [
        {"stage": "INPUT", "at": clock, "title": image_name or "No photograph", "detail": f"{asset_guess} — request held on this host"},
        {"stage": "RETRIEVAL", "at": clock, "title": ", ".join(sorted({h['doc_id'] for h in retrieved})) or "None", "detail": f"{len(retrieved)} passages retrieved from local manuals"},
        {"stage": "VISION", "at": clock, "title": (vision["findings"][0] if vision else "Skipped"), "detail": (
            f"Confidence: {int(confidence * 100)}% ({confidence_kind})" if vision else "No image"
        )},
        {"stage": "EVIDENCE", "at": clock, "title": evidence_panel["observation"]["evidence"].get("citation") or "Evidence not available", "detail": evidence_panel["observation"]["evidence"].get("section") or ""},
        {"stage": "CALCULATION", "at": clock, "title": detail, "detail": "Local arithmetic only"},
        {"stage": "ASSESSMENT", "at": clock, "title": f"AI assessment: Grade {grade}", "detail": f"Confidence: {int(confidence * 100)}% — {confidence_kind}"},
        {"stage": "RECOMMENDATION", "at": clock, "title": recommendation.split('.')[0], "detail": recommendation},
        {"stage": "SECURITY", "at": clock, "title": "External AI APIs: 0", "detail": "Application-level: 0 cloud uploads, 0 AI HTTP clients in this process"},
    ]

    record = audit.log_event(
        {
            "run_id": run_id,
            "kind": "inspection_run",
            "asset": asset_guess,
            "grade": grade,
            "citations": citations,
            "image": image_name,
            "steps": [s["step"] for s in timeline],
            "external_ai_requests": 0,
            "cloud_uploads": 0,
            "telemetry_events": 0,
            "network_isolation_verified": False,
        }
    )
    step("log", f"Audit record committed ({run_id}). External AI requests this run: 0 (application-level).", {"audit": record})

    privacy = {
        "external_ai_requests": 0,
        "cloud_uploads": 0,
        "telemetry_events": 0,
        "local_processing": "100% of this run executed in-process",
        "measurement": "application-level (this process has no cloud AI client). Not a packet capture.",
    }

    return {
        "title": "On-premise inspection note",
        "run_id": run_id,
        "asset": asset_guess,
        "visual_grade": grade,
        "ai_assessment": {
            "grade": grade,
            "basis": "PIP-014-style criteria from retrieved local manuals" if retrieved else "Local rules only — Evidence not available from manuals",
            "confidence": confidence,
            "confidence_pct": int(confidence * 100),
            "confidence_kind": confidence_kind,
            "disclaimer": "AI-assisted assessment — human inspection/engineering approval required before operational decisions.",
        },
        "task": task,
        "observations": observations,
        "vision": vision,
        "calculation": calc,
        "recommendation": recommendation,
        "risk_action": risk_action,
        "why": why,
        "evidence_panel": evidence_panel,
        "prior_report_excerpt": prior_report[:600] if prior_report else None,
        "specs_excerpt": specs[:400] if specs else None,
        "inputs": {
            "asset": asset_guess,
            "photo": image_name,
            "manuals_indexed": extra_docs,
            "prior_report": bool(prior_report),
            "specs": bool(specs),
        },
        "pipeline": ["INPUT", "LOCAL MULTIMODAL ANALYSIS", "OBSERVATIONS", "RETRIEVED EVIDENCE", "CALCULATION", "AI ASSESSMENT", "RECOMMENDATION", "AUDIT TRAIL"],
        "runtime": runtime,
        "privacy": privacy,
        "audit_chain": audit_chain,
        "citations": citations,
        "passages": retrieved,
        "timeline": timeline,
        "audit": record,
        "air_gapped": False,
        "designed_for_airgap": True,
    }
