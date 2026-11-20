"""Capa HTTP: única puerta de salida a internet.

Todo el resto del código recibe un objeto con la interfaz ``Fetcher`` (``get_text`` /
``get_json``) para poder sustituirlo en los tests por ``FakeFetcher`` (sin red).

``HttpFetcher`` es educado: User-Agent genérico (sin datos personales), timeout, caché en
memoria con caducidad, una petición por segundo y host como máximo y respeto de ``robots.txt``.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.robotparser
from typing import Any, Protocol
from urllib.parse import urlencode, urlsplit

USER_AGENT = "Mozilla/5.0 (compatible; pricecheck/0.1; comparador de precios personal)"
TIMEOUT = 12.0
CACHE_TTL = 30 * 60
MIN_INTERVAL = 1.0  # segundos entre peticiones al mismo host


class FetchError(RuntimeError):
    """Fallo de red, HTTP ≥ 400 o bloqueo por robots.txt."""


class Fetcher(Protocol):
    def get_text(self, url: str, params: dict | None = None, headers: dict | None = None,
                 api: bool = False) -> str: ...

    def get_json(self, url: str, params: dict | None = None, headers: dict | None = None,
                 api: bool = True) -> Any: ...


def full_url(url: str, params: dict | None) -> str:
    if not params:
        return url
    return url + ("&" if "?" in url else "?") + urlencode(params)


class HttpFetcher:
    def __init__(self, respect_robots: bool = True, timeout: float = TIMEOUT):
        import requests  # import perezoso: los tests no lo necesitan

        self._s = requests.Session()
        self._s.headers.update({"User-Agent": USER_AGENT,
                                "Accept-Language": "es-ES,es;q=0.9,en;q=0.6"})
        self.timeout = timeout
        self.respect_robots = respect_robots
        self._cache: dict[str, tuple[float, str]] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ internos
    def _allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self._s.get(base + "/robots.txt", timeout=self.timeout)
                rp.parse(r.text.splitlines() if r.status_code < 400 else [])
            except Exception:
                rp = None  # sin robots.txt legible ⇒ permitido
            self._robots[base] = rp
        rp = self._robots[base]
        return rp is None or rp.can_fetch(USER_AGENT, url)

    def _throttle(self, host: str) -> None:
        with self._lock:
            wait = self._last.get(host, 0.0) + MIN_INTERVAL - time.monotonic()
            self._last[host] = time.monotonic() + max(wait, 0.0)
        if wait > 0:
            time.sleep(wait)

    # ------------------------------------------------------------------ API
    def get_text(self, url: str, params: dict | None = None, headers: dict | None = None,
                 api: bool = False) -> str:
        """``api=True`` para APIs documentadas (con o sin clave): robots.txt regula rastreadores
        de páginas, no clientes de una API, y algunas lo prohíben todo para su web."""
        key = full_url(url, params)
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1]
        if not api and not self._allowed(key):
            raise FetchError(f"robots.txt no permite leer {key}")
        self._throttle(urlsplit(key).netloc)
        try:
            r = self._s.get(url, params=params, headers=headers, timeout=self.timeout)
        except Exception as e:  # noqa: BLE001 — cualquier fallo de red es FetchError
            raise FetchError(f"{urlsplit(url).netloc}: {e.__class__.__name__}") from e
        if r.status_code >= 400:
            raise FetchError(f"{urlsplit(url).netloc}: HTTP {r.status_code}")
        self._cache[key] = (time.time(), r.text)
        return r.text

    def get_json(self, url: str, params: dict | None = None, headers: dict | None = None,
                 api: bool = True) -> Any:
        txt = self.get_text(url, params, headers, api=api)
        try:
            return json.loads(txt)
        except json.JSONDecodeError as e:
            raise FetchError(f"{urlsplit(url).netloc}: respuesta no es JSON") from e


class FakeFetcher:
    """Fetcher de tests: ``routes`` asocia un prefijo de URL completa a un texto o a una
    excepción. Gana el prefijo más largo. Registra las URLs pedidas en ``calls``."""

    def __init__(self, routes: dict[str, str | Exception]):
        self.routes = routes
        self.calls: list[str] = []

    def get_text(self, url: str, params: dict | None = None, headers: dict | None = None,
                 api: bool = False) -> str:
        key = full_url(url, params)
        self.calls.append(key)
        match = max((p for p in self.routes if key.startswith(p)), key=len, default=None)
        if match is None:
            raise FetchError(f"sin ruta para {key}")
        val = self.routes[match]
        if isinstance(val, Exception):
            raise val
        return val

    def get_json(self, url: str, params: dict | None = None, headers: dict | None = None,
                 api: bool = True) -> Any:
        return json.loads(self.get_text(url, params, headers, api=api))
