from __future__ import annotations


def test_quant_modules_importable() -> None:
    # 목적: forced_live_autotrade preview 구현 전에 quant 모듈 import 단계에서
    # 문법/구문 오류로 막히지 않음을 최소 수준에서 보장.
    import quant.candidate_score  # noqa: F401
    import quant.scoring_calculator  # noqa: F401
