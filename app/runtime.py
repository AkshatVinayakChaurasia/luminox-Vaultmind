from __future__ import annotations

"""Honest runtime inventory for the prototype.

This workstation does not call cloud AI APIs. It also does not verify OS-level
air-gap (firewall, NIC disable). The UI must keep those two facts distinct.
"""

STACK = [
    {
        "role": "Vision-Language Model",
        "intended": "Qwen2.5-VL-7B (open-weight, local)",
        "actual": "local-color-heuristic",
        "status": "prototype adapter — weights not loaded",
        "local": True,
        "external_api": False,
    },
    {
        "role": "Reasoning Model",
        "intended": "Local open-weight LLM (e.g. Llama 3.x via Ollama)",
        "actual": "on-box inspection agent (rules + retrieved manuals)",
        "status": "prototype agent — LLM weights not loaded",
        "local": True,
        "external_api": False,
    },
    {
        "role": "Embeddings",
        "intended": "BGE-M3 (local)",
        "actual": "lexical token overlap",
        "status": "prototype retrieval — embedding model not loaded",
        "local": True,
        "external_api": False,
    },
    {
        "role": "Vector Store",
        "intended": "On-premise vector index",
        "actual": "local files under data/knowledge",
        "status": "on-disk knowledge base",
        "local": True,
        "external_api": False,
    },
    {
        "role": "Inference",
        "intended": "LOCAL GPU / workstation",
        "actual": "this host (CPU heuristic + local files)",
        "status": "no external AI client configured",
        "local": True,
        "external_api": False,
    },
]

POLICY = {
    "deployment_mode": "Designed for air-gapped / on-premise deployment",
    "execution_policy": "Local execution policy: application does not call external AI APIs",
    "network_isolation": "Not verified by this prototype — OS/firewall is a deployment configuration",
    "telemetry": "This application does not emit product telemetry",
    "data_leaving_this_run": "0 bytes to external AI providers (application-level: no AI HTTP client)",
}


def snapshot() -> dict:
    return {
        "policy": POLICY,
        "stack": STACK,
        "boundary": [
            {"k": "AI inference", "v": "LOCAL (this workstation)", "note": "no cloud AI client"},
            {"k": "Vision processing", "v": "LOCAL", "note": "heuristic adapter until VLM is loaded"},
            {"k": "Document retrieval", "v": "LOCAL", "note": "data/knowledge"},
            {"k": "Embeddings", "v": "LOCAL (lexical stand-in)", "note": "BGE-M3 not loaded"},
            {"k": "Vector database", "v": "LOCAL files", "note": "not a remote vector service"},
            {"k": "Calculations", "v": "LOCAL", "note": "in-process"},
            {"k": "Internet access", "v": "NOT OS-ENFORCED", "note": "deployment configuration"},
            {"k": "External AI APIs", "v": "DISABLED", "note": "no provider keys / clients"},
            {"k": "Data leaving workstation", "v": "0 bytes (app-level)", "note": "this process does not upload to cloud AI"},
        ],
        "badges": [
            {"id": "airgap", "label": "AIR-GAPPED", "title": "Deployment intent. This app does not prove physical isolation."},
            {"id": "onprem", "label": "ON-PREMISE", "title": "Code and knowledge files run on this host."},
            {"id": "nocloud", "label": "NO CLOUD AI", "title": "No OpenAI / Gemini / Anthropic (or similar) client is configured."},
            {"id": "notelemetry", "label": "NO TELEMETRY", "title": "This application does not send product telemetry."},
        ],
    }
