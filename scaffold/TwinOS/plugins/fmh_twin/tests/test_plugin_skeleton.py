"""FMH Plugin 골격 테스트 — Sprint 1에서 실구현 테스트로 대체된다."""

from twinos_sdk import TwinAgent

from plugins.fmh_twin.agent import HIC_D_REGULATORY_LIMIT, FmhTwinAgent


def test_agent_implements_twin_agent_contract():
    assert issubclass(FmhTwinAgent, TwinAgent)
    agent = FmhTwinAgent()
    for method in ("prepare", "run", "validate", "report"):
        assert callable(getattr(agent, method))


def test_regulatory_limit():
    assert HIC_D_REGULATORY_LIMIT == 1000.0
