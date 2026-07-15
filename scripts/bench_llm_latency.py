"""Mesure la latence brute d'Azure AI Inference, sans LangChain ni SDK OpenAI.

But : isoler la latence réseau/backend Azure Foundry de tout overhead
LangChain (retries, chaînes, etc.) — appel HTTP direct sur l'endpoint
`/chat/completions` compatible OpenAI. Log séparé pour comparaison directe
avec `logs/llm_latency.log` (qui, lui, passe par LangChain).

Usage : uv run python scripts/bench_llm_latency.py [--model Kimi-K2.6] [--n 5]
"""

from __future__ import annotations

import argparse
import os
import time
from logging import FileHandler, Formatter, INFO, getLogger

import requests
from dotenv import load_dotenv

load_dotenv()

_logger = getLogger("velmo.bench.latency")
_logger.setLevel(INFO)
_handler = FileHandler("logs/bench_llm_latency.log")
_handler.setFormatter(Formatter("%(asctime)s %(message)s"))
_logger.addHandler(_handler)

# Prompt trivial ("réponds OK") sous-estime la latence réelle : quasi aucun
# token à générer. Un prompt réaliste, proche d'une vraie question client,
# force le modèle à produire une réponse complète — seule mesure comparable
# aux latences observées en usage réel (16-32s constatés en prod).
PROMPT_TRIVIAL = "Réponds uniquement par le mot OK."
PROMPT_REALISTE = "Pourquoi le ciel est bleu ?"


def bench_once(
    endpoint: str, api_key: str, model: str, timeout: float, prompt: str, max_tokens: int
) -> float | None:
    url = f"{endpoint.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": max_tokens,
    }
    start = time.monotonic()
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        latency_ms = (time.monotonic() - start) * 1000
        response.raise_for_status()
        _logger.info("model=%s latency_ms=%.1f status=ok", model, latency_ms)
        return latency_ms
    except requests.exceptions.RequestException as exc:
        latency_ms = (time.monotonic() - start) * 1000
        _logger.info("model=%s latency_ms=%.1f status=error error=%s", model, latency_ms, exc)
        return None


def run_series(endpoint: str, api_key: str, model: str, timeout: float, prompt: str, max_tokens: int, n: int, label: str) -> None:
    print(f"\n{label} — modèle={model}, {n} appels, timeout={timeout}s")
    results = []
    for i in range(n):
        latency = bench_once(endpoint, api_key, model, timeout, prompt, max_tokens)
        status = f"{latency:.0f}ms" if latency is not None else "ÉCHEC"
        print(f"  [{i + 1}/{n}] {status}")
        results.append(latency)

    ok = [r for r in results if r is not None]
    if ok:
        print(f"  → OK: {len(ok)}/{n} — min={min(ok):.0f}ms max={max(ok):.0f}ms avg={sum(ok) / len(ok):.0f}ms")
    else:
        print("  → Aucun appel réussi.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    endpoint = os.environ["AZURE_AI_INFERENCE_ENDPOINT"]
    api_key = os.environ["AZURE_AI_INFERENCE_API_KEY"]
    kimi_model = os.environ.get("AZURE_AI_INFERENCE_MODEL", "Kimi-K2.6")
    phi_model = os.environ.get("AZURE_AI_CLASSIFIER_MODEL", "Phi-4-mini-instruct")

    run_series(endpoint, api_key, kimi_model, args.timeout, PROMPT_TRIVIAL, 5, args.n, "Prompt simple")
    run_series(endpoint, api_key, phi_model, args.timeout, PROMPT_TRIVIAL, 5, args.n, "Prompt simple")
    run_series(endpoint, api_key, kimi_model, args.timeout, PROMPT_REALISTE, 300, args.n, "Prompt réaliste")


if __name__ == "__main__":
    main()
