"""Signaturas de caminos (rough paths) aplicadas al trading (curso §15).

La signatura de un camino ``X: [0, T] → R^d`` es la sucesión de sus integrales iteradas

    S^i = ∫ dX^i,   S^{ij} = ∫∫_{s<u} dX^i_s dX^j_u,   S^{ijk} = ∫∫∫_{s<u<v} dX^i_s dX^j_u dX^k_v, …

Aquí los caminos son lineales a trozos (se unen los datos con segmentos) y la signatura se calcula
exactamente, hasta el nivel 3, con la identidad de Chen (curso §15.2). Convención de arrays: el tiempo
es el eje ``-2`` y los canales el ``-1``; cualquier eje anterior es un lote de trayectorias o ventanas y
todo se vectoriza sobre él.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view


def _as_path(path) -> np.ndarray:
    x = np.asarray(path, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    if x.shape[-2] < 1:
        raise ValueError("el camino necesita al menos un punto")
    return x


def signature(path, depth: int = 2) -> list[np.ndarray]:
    """Signatura truncada ``[S1, S2, S3][:depth]`` de un camino lineal a trozos (curso §15.2).

    ``path`` tiene forma ``(..., n, d)`` (o ``(n,)`` para un solo canal). Devuelve ``S1`` de forma
    ``(..., d)``, ``S2`` de forma ``(..., d, d)`` y ``S3`` de forma ``(..., d, d, d)``.
    Fórmula de Chen con incrementos ``Δ_k`` y sumas previas ``C_k = Σ_{j<k} Δ_j``:

        S2 = Σ_k C_k ⊗ Δ_k + ½ Δ_k^{⊗2},
        S3 = Σ_k S2_{<k} ⊗ Δ_k + ½ C_k ⊗ Δ_k^{⊗2} + ⅙ Δ_k^{⊗3}.
    """
    if depth not in (1, 2, 3):
        raise ValueError("depth debe ser 1, 2 o 3")
    x = _as_path(path)
    dx = np.diff(x, axis=-2)
    s1 = dx.sum(axis=-2)
    out = [s1]
    if depth == 1:
        return out
    c = np.cumsum(dx, axis=-2) - dx                        # C_k: incremento acumulado antes del tramo k
    t2 = np.einsum("...ki,...kj->...kij", c + 0.5 * dx, dx)  # aportación de cada tramo al nivel 2
    out.append(t2.sum(axis=-3))
    if depth == 2:
        return out
    s2_prev = np.cumsum(t2, axis=-3) - t2                  # S2 del camino hasta el inicio del tramo k
    s3 = (np.einsum("...kij,...kl->...ijl", s2_prev, dx)
          + np.einsum("...ki,...kj,...kl->...ijl", 0.5 * c + dx / 6.0, dx, dx))
    out.append(s3)
    return out


def flatten(sig: list[np.ndarray]) -> np.ndarray:
    """Concatena los niveles de una signatura en un vector de rasgos ``(..., d + d² + d³)``."""
    lead = sig[0].shape[:-1]
    return np.concatenate([s.reshape(*lead, -1) for s in sig], axis=-1)


def levy_area(path) -> np.ndarray:
    """Área de Lévy ``A^{ij} = ½(S^{ij} − S^{ji})`` (curso §15.4), matriz antisimétrica ``(..., d, d)``.

    Para un lazo cerrado es el área encerrada con signo (positiva si se recorre en sentido antihorario).
    ``A^{12} > 0`` indica que el canal 1 tiende a moverse *antes* que el canal 2.
    """
    s2 = signature(path, 2)[1]
    return 0.5 * (s2 - np.swapaxes(s2, -1, -2))


def log_signature2(path) -> tuple[np.ndarray, np.ndarray]:
    """Log-signatura de nivel 2: ``(S1, A)``, con ``A`` el área de Lévy (curso §15.2).

    Identidad de barajado de nivel 2: ``S2 = ½ S1⊗S1 + A``; la parte simétrica de S2 no aporta
    información nueva y basta con el incremento y el área.
    """
    s1, s2 = signature(path, 2)
    return s1, 0.5 * (s2 - np.swapaxes(s2, -1, -2))


def lead_lag(x) -> np.ndarray:
    """Transformación lead-lag (curso §15.3): de ``(..., n, d)`` a ``(..., 2n−1, 2d)``.

    Los canales ``[:d]`` son la copia adelantada (*lead*) y ``[d:]`` la retrasada (*lag*): primero se
    mueve la copia adelantada y después la retrasada la alcanza. El área de Lévy entre ambas copias de
    un mismo canal es la mitad de su variación cuadrática, ``½ Σ (Δx_k)²``.
    """
    p = _as_path(x)
    rep = np.repeat(p, 2, axis=-2)
    return np.concatenate([rep[..., 1:, :], rep[..., :-1, :]], axis=-1)


def add_time(path, t=None) -> np.ndarray:
    """Antepone el canal de tiempo (por defecto ``0 … 1`` uniforme) al camino (curso §15.2).

    Con el tiempo como canal la signatura deja de ser invariante por reparametrización: vuelve a
    distinguir un movimiento rápido de uno lento.
    """
    p = _as_path(path)
    n = p.shape[-2]
    t = np.linspace(0.0, 1.0, n) if t is None else np.asarray(t, dtype=float)
    tt = np.broadcast_to(t[:, None], (*p.shape[:-2], n, 1))
    return np.concatenate([tt, p], axis=-1)


def lead_lag_score(rx, ry, window: int = 20) -> tuple[float, float]:
    """Puntuación de liderazgo de ``x`` sobre ``y`` con el área de Lévy (curso §15.4).

    Se estandarizan las rentabilidades, se acumulan en ventanas sin solape de ``window`` periodos y se
    promedia el área ``A^{xy}`` normalizada por ``(w−1)/2``. Su esperanza es

        Σ_{h=1}^{w−1} (w−h)/(w−1) · [ρ_{x→y}(h) − ρ_{y→x}(h)],   ρ_{x→y}(h) = corr(r^x_t, r^y_{t+h}),

    es decir ``ρ_{x→y}(1) − ρ_{y→x}(1)`` cuando sólo hay desfase de un periodo. Positiva: x lidera.
    Devuelve ``(puntuación, error típico)`` (error típico entre ventanas).
    """
    rx = np.asarray(rx, dtype=float)
    ry = np.asarray(ry, dtype=float)
    if rx.shape != ry.shape or rx.ndim != 1:
        raise ValueError("rx y ry deben ser vectores de la misma longitud")
    if window < 2 or len(rx) < 2 * window:
        raise ValueError("hacen falta al menos dos ventanas de longitud ≥ 2")
    z = np.column_stack([(rx - rx.mean()) / rx.std(), (ry - ry.mean()) / ry.std()])
    m = len(z) // window
    blocks = z[: m * window].reshape(m, window, 2)
    paths = np.concatenate([np.zeros((m, 1, 2)), np.cumsum(blocks, axis=1)], axis=1)
    a = levy_area(paths)[:, 0, 1] / (0.5 * (window - 1))
    return float(a.mean()), float(a.std(ddof=1) / np.sqrt(m))


def window_features(close: pd.Series, window: int = 20, depth: int = 2) -> pd.DataFrame:
    """Rasgos de signatura de la ventana que termina en cada fecha (sólo pasado, curso §15.5).

    Camino de la ventana: ``(tiempo, log-precio relativo / vol de la ventana)`` con su transformación
    lead-lag en el canal de precio. Se quitan los términos constantes (los del tiempo puro). Las
    primeras ``window − 1`` filas son NaN.
    """
    lp = np.log(close.to_numpy(dtype=float))
    n = len(lp)
    if window < 3:
        raise ValueError("la ventana debe tener al menos 3 sesiones")
    if n < window:
        raise ValueError("serie más corta que la ventana")
    w = sliding_window_view(lp, window)                       # (n − window + 1, window)
    rel = w - w[:, :1]
    vol = np.diff(w, axis=1).std(axis=1, ddof=1)
    rel = rel / np.where(vol > 0, vol, 1.0)[:, None]
    ll = lead_lag(rel[..., None])                              # (m, 2·window − 1, 2)
    t = np.repeat(np.linspace(0.0, 1.0, window), 2)[1:]       # tiempo del camino lead-lag
    feats = flatten(signature(add_time(ll, t), depth))
    names = _names(3, depth)
    keep = np.array([set(nm) != {"t"} for nm in names])    # fuera los términos de tiempo puro (constantes)
    feats = feats[:, keep]
    cols = [nm for nm, k in zip(names, keep) if k]
    out = np.full((n, feats.shape[1]), np.nan)
    out[window - 1:] = feats
    return pd.DataFrame(out, index=close.index, columns=cols)


def _names(d: int, depth: int) -> list[str]:
    ch = "tpq"  # tiempo, precio adelantado, precio retrasado
    names = list(ch[:d])
    if depth >= 2:
        names += [a + b for a in ch[:d] for b in ch[:d]]
    if depth >= 3:
        names += [a + b + c for a in ch[:d] for b in ch[:d] for c in ch[:d]]
    return names


def sig_momentum(close: pd.Series, window: int = 20, depth: int = 2, train: int = 500, refit: int = 63,
                 ridge: float = 10.0) -> pd.Series:
    """Estrategia lineal sobre la signatura con reestimación walk-forward (curso §15.5).

    En cada reestimación (cada ``refit`` sesiones) se ajusta una regresión ridge de la rentabilidad del
    día siguiente sobre los rasgos de :func:`window_features`, usando sólo las ``train`` sesiones
    anteriores cuyo resultado ya se conoce. La posición es el signo de la predicción (+1/−1); antes del
    primer ajuste es 0. Sin look-ahead: la posición de t sólo usa precios hasta t.
    """
    if len(close) <= train + window:
        raise ValueError(f"hacen falta más de {train + window} sesiones (entrenamiento + ventana)")
    x = window_features(close, window, depth)
    y = np.log(close).diff().shift(-1)                         # objetivo: rentabilidad t → t+1
    pos = pd.Series(0.0, index=close.index)
    xv, yv = x.to_numpy(), y.to_numpy()
    n = len(close)
    for start in range(train + window, n, refit):              # un ajuste por bloque, no por día
        lo = start - train
        # Muestras con objetivo conocido en ``start``: rasgos en t ≤ start − 1, objetivo r_{t+1} ≤ r_start.
        xs, ys = xv[lo:start], yv[lo:start]
        ok = ~np.isnan(xs).any(axis=1) & ~np.isnan(ys)
        xs, ys = xs[ok], ys[ok]
        mu, sd = xs.mean(axis=0), xs.std(axis=0)
        sd = np.where(sd > 0, sd, 1.0)
        zs = (xs - mu) / sd
        beta = np.linalg.solve(zs.T @ zs + ridge * np.eye(zs.shape[1]), zs.T @ (ys - ys.mean()))
        end = min(start + refit, n)
        pred = ((xv[start:end] - mu) / sd) @ beta + ys.mean()
        pos.iloc[start:end] = np.sign(pred)
    return pos
