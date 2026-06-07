"""Thin HTTP transport for fiscalization providers.

Reads per-country endpoint/credentials from ``settings.FISCALIZATION``. Adapters
call :func:`provider_config` to decide between live submission and the sandbox.
"""
import requests
from django.conf import settings


class FiscalizationTransportError(Exception):
    """Raised when the provider call fails (network/HTTP/parse)."""


def provider_config(country: str) -> dict:
    return settings.FISCALIZATION.get(country, {})


def is_live(country: str) -> bool:
    return bool(provider_config(country).get("endpoint"))


def post_json(country: str, body: str, content_type: str = "application/json") -> dict:
    """POST a serialized payload to the provider and return the JSON response.

    Authentication is a bearer API key (the common pattern for both an FTA ASP
    and an FBR licensed integrator). Raises on any non-2xx or transport error so
    the Celery task can retry with backoff.
    """
    cfg = provider_config(country)
    endpoint = cfg.get("endpoint")
    if not endpoint:
        raise FiscalizationTransportError(f"No fiscalization endpoint configured for {country}.")
    headers = {"Content-Type": content_type}
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    try:
        resp = requests.post(endpoint, data=body.encode("utf-8"), headers=headers,
                             timeout=cfg.get("timeout", 20))
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise FiscalizationTransportError(str(exc)) from exc
