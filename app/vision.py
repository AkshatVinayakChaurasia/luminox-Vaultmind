from __future__ import annotations

from pathlib import Path

from PIL import Image


def inspect_image(path: Path) -> dict:
    """Prototype on-box vision: color/texture cues, not a foundation model.

    Replace this adapter later with a local VL runtime (e.g. Ollama + Qwen2.5-VL)
    without changing the agent contract.
    """
    img = Image.open(path).convert("RGB")
    w, h = img.size
    img_small = img.resize((160, max(1, int(160 * h / w))))
    pixels = list(img_small.getdata())
    n = len(pixels) or 1
    rust = oil = bright = 0
    rs = gs = bs = 0
    for r, g, b in pixels:
        rs += r
        gs += g
        bs += b
        if r > 95 and r > g * 1.25 and r > b * 1.35 and g < 140:
            rust += 1
        if r < 70 and g < 70 and b < 70:
            oil += 1
        if r > 200 and g > 200 and b > 200:
            bright += 1
    rust_frac = rust / n
    oil_frac = oil / n
    findings: list[str] = []
    grade_hint = "A"
    if rust_frac > 0.18:
        findings.append(
            "Widespread orange-brown surface consistent with general rust / scab corrosion."
        )
        grade_hint = "C"
    elif rust_frac > 0.07:
        findings.append("Scattered rust staining on painted or bare metal surfaces.")
        grade_hint = "B"
    elif rust_frac > 0.02:
        findings.append("Light rust discoloration; mill scale or light atmospheric rust possible.")
        grade_hint = "A"
    else:
        findings.append("No strong rust-colored dominance in the frame; visual corrosion is not obvious from color alone.")

    if oil_frac > 0.12:
        findings.append("Dark low-reflectance regions that may indicate oil wetness, product residue, or heavy scale.")
        if grade_hint in {"A", "B"}:
            grade_hint = "C"

    if not findings:
        findings.append("Image ingested; insufficient chromatic evidence for a confident visual grade.")

    # Prototype score from chromatic cues — not a calibrated VLM probability.
    cue = min(0.34, rust_frac * 1.2 + oil_frac * 0.4)
    confidence = round(min(0.91, 0.52 + cue), 2)

    return {
        "filename": path.name,
        "width": w,
        "height": h,
        "mode": "on-premise-heuristic-vision",
        "model": "local-color-heuristic (swap-in: Qwen2.5-VL)",
        "rust_fraction": round(rust_frac, 3),
        "dark_fraction": round(oil_frac, 3),
        "mean_rgb": [round(rs / n), round(gs / n), round(bs / n)],
        "findings": findings,
        "visual_grade_hint": grade_hint,
        "confidence": confidence,
        "confidence_kind": "heuristic prototype score",
        "egress": "none — pixels never left this host",
    }
