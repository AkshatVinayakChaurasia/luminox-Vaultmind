from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = ROOT / "data" / "knowledge"

_TOKEN = re.compile(r"[a-z0-9]{2,}")
_PAGE = re.compile(r"--- PAGE (\d+) ---", re.I)


@dataclass
class Chunk:
    doc_id: str
    title: str
    revision: str
    page: int
    text: str
    tokens: set[str] = field(default_factory=set)


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def parse_document(path: Path) -> list[Chunk]:
    raw = path.read_text(encoding="utf-8")
    header: dict[str, str] = {}
    for line in raw.splitlines()[:8]:
        if ":" in line and not line.startswith("---"):
            k, v = line.split(":", 1)
            header[k.strip().upper()] = v.strip()
    doc_id = header.get("DOCUMENT", path.stem)
    title = header.get("TITLE", path.stem)
    revision = header.get("REVISION", "—")
    parts = _PAGE.split(raw)
    chunks: list[Chunk] = []
    if len(parts) == 1:
        text = raw.strip()
        chunks.append(Chunk(doc_id, title, revision, 1, text, _tokens(text)))
        return chunks
    # split: [preamble, page, body, page, body, ...]
    for i in range(1, len(parts), 2):
        page = int(parts[i])
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if not body:
            continue
        chunks.append(Chunk(doc_id, title, revision, page, body, _tokens(body)))
    return chunks


class KnowledgeBase:
    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self.reload()

    def reload(self) -> None:
        self.chunks = []
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        for path in sorted(KNOWLEDGE_DIR.glob("*")):
            if path.suffix.lower() in {".txt", ".md"}:
                self.chunks.extend(parse_document(path))

    def ingest_text(self, doc_id: str, title: str, text: str, revision: str = "upload") -> int:
        fake = (
            f"DOCUMENT: {doc_id}\nREVISION: {revision}\nTITLE: {title}\n\n{text}"
        )
        path = KNOWLEDGE_DIR / f"upload-{doc_id}.txt"
        path.write_text(fake, encoding="utf-8")
        new_chunks = parse_document(path)
        self.chunks.extend(new_chunks)
        return len(new_chunks)

    def search(self, query: str, extra: str = "", k: int = 4) -> list[dict]:
        q = _tokens(f"{query} {extra}")
        if not q or not self.chunks:
            return []
        scored: list[tuple[float, Chunk]] = []
        for ch in self.chunks:
            overlap = q & ch.tokens
            if not overlap:
                continue
            idf_like = len(overlap) / math.sqrt(len(ch.tokens) + 1)
            bonus = 0.35 if any(w in ch.text.lower() for w in ("grade", "thickness", "corrosion", "leak")) else 0
            scored.append((idf_like + bonus, ch))
        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for score, ch in scored[:k]:
            section = (ch.text.strip().splitlines() or [""])[0].strip()[:160]
            out.append(
                {
                    "doc_id": ch.doc_id,
                    "title": ch.title,
                    "revision": ch.revision,
                    "page": ch.page,
                    "section": section or None,
                    "score": round(score, 3),
                    "excerpt": ch.text.strip()[:900],
                    "citation": f"{ch.doc_id} ({ch.revision}) — Page {ch.page}",
                }
            )
        return out

    def catalog(self) -> list[dict]:
        seen: dict[str, dict] = {}
        for ch in self.chunks:
            rec = seen.setdefault(
                ch.doc_id,
                {"doc_id": ch.doc_id, "title": ch.title, "revision": ch.revision, "pages": set()},
            )
            rec["pages"].add(ch.page)
        rows = []
        for rec in seen.values():
            rows.append(
                {
                    "doc_id": rec["doc_id"],
                    "title": rec["title"],
                    "revision": rec["revision"],
                    "pages": sorted(rec["pages"]),
                }
            )
        return rows


def extract_text_from_upload(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            pages = []
            for i, page in enumerate(reader.pages, start=1):
                pages.append(f"--- PAGE {i} ---\n{(page.extract_text() or '').strip()}")
            return "\n\n".join(pages) or path.name
        except Exception:
            # malformed / encrypted / image-only PDF — keep the run alive
            return f"[{path.name}: no extractable text]"
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return f"[{path.name}: unreadable]"
