"""Modal GPU deployment for an OpenAI-compatible llama.cpp endpoint.

Deploy with ``modal deploy modal_slm.py`` after creating the ``automoat-slm``
secret containing AUTOMOAT_SLM_TOKEN and, for gated models, HF_TOKEN.
"""

import json
import os
import secrets
import time
from typing import Any

import modal


MODEL_REPO = os.environ.get(
    "AUTOMOAT_SLM_MODEL_REPO",
    "bartowski/Qwen2.5-3B-Instruct-GGUF",
)
MODEL_FILE = os.environ.get("AUTOMOAT_SLM_MODEL_FILE", "Qwen2.5-3B-Instruct-Q4_K_M.gguf")
MODEL_DIR = "/models"

app = modal.App("automoat-slm")
model_volume = modal.Volume.from_name("automoat-slm-models", create_if_missing=True)
image = (
    modal.Image.from_registry("nvidia/cuda:12.4.1-devel-ubuntu22.04", add_python="3.11")
    .apt_install("build-essential", "cmake", "git")
    .pip_install("huggingface-hub==0.33.4", "fastapi[standard]==0.116.1")
    .run_commands(
        'CMAKE_ARGS="-DGGML_CUDA=on" CMAKE_BUILD_PARALLEL_LEVEL=8 '
        "pip install llama-cpp-python==0.3.16"
    )
)


@app.cls(
    image=image,
    gpu="L4",
    timeout=600,
    scaledown_window=300,
    volumes={MODEL_DIR: model_volume},
    secrets=[modal.Secret.from_name("automoat-slm")],
)
@modal.concurrent(max_inputs=4)
class LlamaCppModel:
    @modal.enter()
    def load(self):
        from huggingface_hub import hf_hub_download
        from llama_cpp import Llama

        model_path = hf_hub_download(
            repo_id=MODEL_REPO,
            filename=MODEL_FILE,
            local_dir=MODEL_DIR,
            token=os.environ.get("HF_TOKEN") or None,
        )
        model_volume.commit()
        self.model = Llama(
            model_path=model_path,
            n_ctx=8192,
            n_gpu_layers=-1,
            verbose=False,
        )

    @modal.method()
    def completions(self, request: dict[str, Any]) -> dict[str, Any]:
        messages = request.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages must be a non-empty list")
        started = time.monotonic()
        result = self.model.create_chat_completion(
            messages=messages,
            temperature=max(0.0, min(float(request.get("temperature", 0)), 1.0)),
            response_format=request.get("response_format"),
            max_tokens=min(int(request.get("max_tokens", 512)), 1024),
        )
        result["model"] = MODEL_REPO
        result["automoat"] = {"latency_ms": round((time.monotonic() - started) * 1000)}
        return json.loads(json.dumps(result, allow_nan=False))


@app.function(image=image, secrets=[modal.Secret.from_name("automoat-slm")])
@modal.asgi_app()
def api():
    from fastapi import FastAPI, HTTPException, Request

    web = FastAPI(title="automoat SLM", docs_url=None, redoc_url=None)

    @web.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "model": MODEL_REPO}

    @web.post("/v1/chat/completions")
    async def completions(request: Request) -> dict[str, Any]:
        expected = os.environ.get("AUTOMOAT_SLM_TOKEN", "")
        supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        if not expected or not secrets.compare_digest(supplied, expected):
            raise HTTPException(status_code=401, detail="unauthorized")
        try:
            payload = await request.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="invalid JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="request body must be an object")
        try:
            return LlamaCppModel().completions.remote(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return web
