"""HIC 계산 단위 테스트 — 판정 일치율 검증(WBS 2.5)의 기반."""

import math

from libs.cae_toolkit.hic import hic36, hic_d


def _const_signal(g: float, duration_s: float, dt: float = 1e-4):
    n = int(duration_s / dt) + 1
    t = [i * dt for i in range(n)]
    a = [g] * n
    return t, a


def test_hic36_constant_acceleration_long_pulse():
    # 일정 가속도 c[g], 지속시간 T > 36ms → HIC36 = c^2.5 * 0.036
    t, a = _const_signal(100.0, 0.100)
    expected = 100.0**2.5 * 0.036
    assert math.isclose(hic36(t, a), expected, rel_tol=1e-3)


def test_hic36_constant_acceleration_short_pulse():
    # 지속시간 T < 36ms → 창이 T로 제한: HIC36 = c^2.5 * T
    t, a = _const_signal(100.0, 0.010)
    expected = 100.0**2.5 * 0.010
    assert math.isclose(hic36(t, a), expected, rel_tol=1e-3)


def test_hic_d_linear_transform():
    t, a = _const_signal(100.0, 0.100)
    assert math.isclose(hic_d(t, a), 0.75446 * hic36(t, a) + 166.4, rel_tol=1e-12)


def test_zero_signal():
    t, a = _const_signal(0.0, 0.050)
    assert hic36(t, a) == 0.0
