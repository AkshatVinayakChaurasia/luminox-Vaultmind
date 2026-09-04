# VaultMind — Sovereign AI Workbench

**Team Luminox**

An on-premise industrial inspection agent. The marketing landing page and the working
inspection console are served by the same FastAPI process, so the whole thing deploys as
one unit. Nothing in this build calls a cloud AI provider.

| Route | What it is |
|---|---|
| `/` | VaultMind landing page |
| `/console` | Inspection workbench (the working product) |

Every **Access Workbench / Explore Workbench** button on the landing page opens `/console`,
so the two halves are wired together.

---

## Run it locally

**Windows (PowerShell)**
```powershell
cd vaultmind
.\run.ps1
```

**macOS / Linux**
```bash
cd vaultmind
./run.sh
```

**Manually**
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Then open <http://127.0.0.1:8080/>.

---

## Deploy it

The app reads `PORT` from the environment and binds `0.0.0.0`, so it works on every common
platform without changes.

### Docker (works anywhere)
```bash
docker build -t vaultmind .
docker run -p 8080:8080 vaultmind
```

### Render
Push the repo and pick **Blueprint** — `render.yaml` is already in the root. Or configure
manually:
- Build command — `pip install -r requirements.txt`
- Start command — `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check path — `/healthz`


### Heroku / Fly / any Procfile host
`Procfile` is in the root:
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Environment variables (all optional)

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8080` | port to bind |
| `HOST` | `0.0.0.0` | interface to bind |
| `VAULTMIND_MAX_UPLOAD_MB` | `25` | per-file upload cap |

### One thing to know before you deploy

`data/uploads`, `data/audit` and any manual you upload are written to the container's
filesystem. On ephemeral hosts (Render free, Railway, Heroku) that disk is wiped on every
restart, so the audit trail resets. That is fine for a demo. For a persistent trail , mount a
volume at `/app/data`.

The pages load Inter and IBM Plex Mono from Google Fonts. If you demo fully offline, the
system font fallbacks take over and the layout stays intact — nothing breaks, the type just
looks slightly different.

---

## Run it in VS Code

A `.vscode/` folder is already included — extract the zip, then in VS Code:
**File → Open Folder…** → select the `vaultmind` folder.

**1. Install the Python extension** (VS Code will prompt you — accept it, or install
`ms-python.python` manually from the Extensions panel).

**2. Create the virtual environment.**
Open a terminal in VS Code (`` Ctrl+` `` / `` Cmd+` ``) and run:
```bash
python -m venv .venv
```
Windows:
```powershell
python -m venv .venv
```
VS Code will pop up "Select environment for your workspace" — pick `.venv`. If it doesn't
ask, open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`) → **Python: Select
Interpreter** → choose the one inside `.venv`.

Or skip both steps above and just run the included task:
**Terminal → Run Task… → "VaultMind: Create venv + install deps"**.

**3. Install dependencies** (skip if you used the task above):
```bash
.venv/bin/pip install -r requirements.txt          # macOS/Linux
.\.venv\Scripts\pip install -r requirements.txt    # Windows
```

**4. Run it.** Three ways, pick whichever you like:
- Press **F5** — starts `uvicorn` with auto-reload and a debugger attached; set
  breakpoints in `app/agent.py` etc. and they'll hit on the next request.
- **Terminal → Run Task… → "VaultMind: Run server"** — same thing, no debugger.
- Or just type it into the terminal:
  ```bash
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
  ```

Then open <http://127.0.0.1:8080/> for the landing page or
<http://127.0.0.1:8080/console> for the workbench. `--reload` means editing any `.py` file
restarts the server automatically — no need to stop and re-run.

**Editing the frontend:** `frontend/index.html` and `frontend/console.html` are plain
HTML/CSS/JS with no build step. Right-click either file → **Open with Live Server** for
instant preview while styling, but remember the *working* version — the one wired to the
API — is always served through the FastAPI app at `/` and `/console`, not through Live
Server's own port.

---


1. Understands the inspection request
2. Retrieves passages from the local manuals in `data/knowledge/`
3. Inspects an uploaded photo with an on-box colour heuristic (stand-in for a local VLM)
4. Reasons over image + prior report + specifications
5. Runs a remaining-wall vs retirement calculation when a thickness in mm is present
6. Writes a recommendation
7. Cites document id, revision and page
8. Appends the run to the local audit trail

Manuals already loaded: **PIP-014 R4**, **SOP-PUMP-032 R2**, **SPEC-HX-441 A**.

Uploaded manuals are indexed into the same knowledge base. Uploads stay under
`data/uploads/`. Audit events append to `data/audit/audit.jsonl`.

---

## Layout

```
vaultmind/
├── app/
│   ├── main.py        FastAPI routes, gzip, upload limits, error handling
│   ├── agent.py       inspection pipeline
│   ├── knowledge.py   local document parsing + lexical retrieval
│   ├── vision.py      on-box image adapter
│   ├── audit.py       append-only local audit log
│   └── runtime.py     runtime / boundary inventory
├── frontend/
│   ├── index.html     VaultMind landing page
│   └── console.html   inspection workbench (same design system)
├── data/
│   ├── knowledge/     local manuals
│   ├── uploads/       user uploads stay here
│   └── audit/         audit.jsonl
├── Dockerfile · Procfile · render.yaml · railway.json · runtime.txt
├── requirements.txt
├── run.ps1 · run.sh
└── README.md
```

## Intentionally out of scope for this build

- Full VL / LLM weights — the vision and reasoning adapters are local stand-ins
- OS/network-level air-gap enforcement — that is a deployment configuration, not something
  the application can certify. The console deliberately keeps *application policy* and
  *physical guarantee* separate rather than overclaiming.
