"""Daydreams Router API client helpers."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import logging

import requests

_DEFAULT_BASE_URL = "https://api-beta.daydreams.systems/v1"

logger = logging.getLogger(__name__)


class DaydreamsRouterClient:
    """Lightweight wrapper around the Daydreams Router REST API."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: Optional[str] = None,
        timeout: int = 30,
        session: Optional[requests.Session] = None,
    ) -> None:
        if not api_key:
            raise ValueError("DAYDREAMS_API_KEY is required for Daydreams Router provider")

        self.api_key = api_key
        self.base_url = (base_url or os.getenv("DAYDREAMS_BASE_URL") or _DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )

    # -----------------
    # Internal utilities
    # -----------------

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self.base_url}{path}"

    # -------------------
    # Public API wrappers
    # -------------------

    def submit_video_job(self, model: str, payload: Dict[str, Any], *, slug: Optional[str] = None) -> Dict[str, Any]:
        base_body = {"model": model}
        base_body.update(payload)

        candidate_slug = slug or (model.split("/")[-1] if model else None)
        paths = []
        if candidate_slug:
            paths.append(f"/videos/{candidate_slug}/jobs")
        paths.append("/videos/jobs")

        last_error: Optional[requests.Response] = None
        for path in paths:
            body = base_body.copy()
            if path != "/videos/jobs":
                body.pop("model", None)
            logger.info("daydreams: POST %s payload=%s", path, body)
            resp = self.session.post(
                self._url(path),
                json=body,
                timeout=self.timeout,
            )
            logger.info(
                "daydreams: response %s status=%s", path, resp.status_code
            )
            if resp.status_code == 404 and path != paths[-1]:
                last_error = resp
                continue
            resp.raise_for_status()
            return resp.json()

        if last_error is not None:
            last_error.raise_for_status()
        raise RuntimeError("Failed to submit Daydreams Router video job")

    def get_video_job(self, job_id: str) -> Dict[str, Any]:
        logger.info("daydreams: GET /videos/jobs/%s", job_id)
        resp = self.session.get(
            self._url(f"/videos/jobs/{job_id}"),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("job", data)

    def fetch_job_status(self, status_url: str) -> Dict[str, Any]:
        logger.info("daydreams: GET status_url=%s", status_url)
        resp = self.session.get(
            self._url(status_url),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("job", data)

    def list_models(self) -> Dict[str, Any]:
        resp = self.session.get(
            self._url("/models"),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def download_asset(self, asset_url: str, output_path) -> None:
        with self.session.get(self._url(asset_url), stream=True, timeout=self.timeout) as resp:
            resp.raise_for_status()
            with open(output_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        fh.write(chunk)

    def create_chat_completion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = self.session.post(
            self._url("/chat/completions"),
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

__all__ = ["DaydreamsRouterClient"]
