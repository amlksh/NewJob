"""HIC (Head Injury Criterion) 계산 — FMH Twin의 핵심 QoI (08 문서 §2).

HIC = max over (t1, t2), t2-t1 <= window:
      (t2 - t1) * [ (1/(t2-t1)) * ∫ a(t) dt ]^2.5
a(t)는 g 단위 합성 가속도, t는 초.
HIC(d) = 0.75446 * HIC36 + 166.4  (FMVSS 201U free motion headform)
"""

from __future__ import annotations

from bisect import bisect_right


def _cumulative_trapezoid(t: list[float], a: list[float]) -> list[float]:
    acc = [0.0]
    for i in range(1, len(t)):
        acc.append(acc[-1] + 0.5 * (a[i] + a[i - 1]) * (t[i] - t[i - 1]))
    return acc


def hic(t: list[float], a: list[float], window_s: float) -> float:
    """가속도 시계열(t[s], a[g])에 대한 HIC. O(n^2)이나 해석 출력 규모에서 충분."""
    if len(t) != len(a):
        raise ValueError("t and a must have equal length")
    if len(t) < 2:
        return 0.0
    if any(t[i + 1] <= t[i] for i in range(len(t) - 1)):
        raise ValueError("t must be strictly increasing")

    cum = _cumulative_trapezoid(t, a)
    best = 0.0
    for i in range(len(t) - 1):
        j_max = bisect_right(t, t[i] + window_s, lo=i + 1)
        for j in range(i + 1, j_max):
            dt = t[j] - t[i]
            avg = (cum[j] - cum[i]) / dt
            if avg <= 0.0:
                continue
            best = max(best, dt * avg**2.5)
    return best


def hic36(t: list[float], a: list[float]) -> float:
    return hic(t, a, 0.036)


def hic15(t: list[float], a: list[float]) -> float:
    return hic(t, a, 0.015)


def hic_d(t: list[float], a: list[float]) -> float:
    """FMVSS 201U HIC(d)."""
    return 0.75446 * hic36(t, a) + 166.4
