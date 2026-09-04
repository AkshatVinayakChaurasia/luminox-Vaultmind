from __future__ import annotations

import os
import traceback
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.agent import run_inspection
from app.audit import recent
from app.knowledge import KnowledgeBase, extract_text_from_upload
from app.runtime import snapshot as runtime_snapshot

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
UPLOADS = ROOT / "data" / "uploads"
LANDING = FRONTEND / "index.html"
CONSOLE = FRONTEND / "console.html"

# a single upload is capped so one bad request cannot fill the disk
MAX_UPLOAD_BYTES = int(os.getenv("VAULTMIND_MAX_UPLOAD_MB", "25")) * 1024 * 1024

kb = KnowledgeBase()

app = FastAPI(
    title="VaultMind Sovereign AI Workbench",
    description="On-premise inspection agent - Team Luminox.",
    version="1.0.0",
)

# the landing page is one large HTML document; gzip keeps the transfer small
app.add_middleware(GZipMiddleware, minimum_size=1024)

app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")


@app.get("/", include_in_schema=False)
def landing():
    return FileResponse(LANDING, media_type="text/html")


@app.get("/console", include_in_schema=False)
def console():
    return FileResponse(CONSOLE, media_type="text/html")


@app.get("/healthz", include_in_schema=False)
def healthz():
    """Plain liveness probe for platform health checks."""
    return {"status": "ok"}


@app.get("/api/health")
def health():
    snap = runtime_snapshot()
    return {
        "ok": True,
        "mode": "on-premise-prototype",
        "designed_for_airgap": True,
        "network_isolation_verified": False,
        "external_ai_apis": "disabled",
        "documents": len(kb.catalog()),
        "runtime": snap,
    }


@app.get("/api/knowledge")
def knowledge():
    return {"documents": kb.catalog()}


@app.get("/api/audit")
def audit_log():
    return {"events": recent()}


@app.post("/api/inspect")
async def inspect(
    request: str = Form(""),
    specs: str = Form(""),
    prior_report_text: str = Form(""),
    image: UploadFile | None = File(None),
    prior_report: UploadFile | None = File(None),
    manual: UploadFile | None = File(None),
    spec_file: UploadFile | None = File(None),
):
    UPLOADS.mkdir(parents=True, exist_ok=True)
    extra_docs: list[str] = []
    image_path = None

    async def save(upload: UploadFile | None) -> Path | None:
        """Stream an upload to disk, refusing anything over the size cap."""
        if not upload or not upload.filename:
            return None
        safe_name = Path(upload.filename).name.replace("\\", "_")
        dest = UPLOADS / f"{uuid.uuid4().hex[:8]}-{safe_name}"
        written = 0
        with dest.open("wb") as fh:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    fh.close()
                    dest.unlink(missing_ok=True)
                    raise ValueError(
                        f"{safe_name} exceeds the "
                        f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit"
                    )
                fh.write(chunk)
        return dest

    try:
        img = await save(image)
        if img:
            image_path = str(img)

        prior = prior_report_text
        pr = await save(prior_report)
        if pr:
            prior = (prior + "\n" + extract_text_from_upload(pr)).strip()
            extra_docs.append(pr.name)

        man = await save(manual)
        if man:
            text = extract_text_from_upload(man)
            kb.ingest_text(Path(man.name).stem, man.name, text)
            extra_docs.append(man.name)

        sf = await save(spec_file)
        spec_blob = specs
        if sf:
            spec_blob = (spec_blob + "\n" + extract_text_from_upload(sf)).strip()
            extra_docs.append(sf.name)

        report = run_inspection(
            {
                "request": request,
                "image_path": image_path,
                "prior_report": prior,
                "specs": spec_blob,
                "extra_docs": extra_docs,
            },
            kb,
        )
        return JSONResponse(report)

    except ValueError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=413)
    except Exception as exc:  # never hand the console an opaque 500
        traceback.print_exc()
        return JSONResponse(
            {"detail": f"Inspection failed on this host: {type(exc).__name__} - {exc}"},
            status_code=500,
        )


if __name__ == "__main__":  # `python -m app.main` also works
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8080")),
    )
