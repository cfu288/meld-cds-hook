import pytest
from datetime import datetime
from meld_cds_hook.main import calculate_meld_score, MeldScoreParams

def test_calculate_meld_score():
    params = MeldScoreParams(
        sex="male",
        bilirubin=1.2,
        sodium=135,
        inr=1.1,
        albumin=3.0,
        creatinine=1.5,
        had_dialysis=False,
        dob=datetime(1990, 1, 1)
    )
    score = calculate_meld_score(params)
    assert score is not None
    assert score == 14  # Expected MELD score based on provided values

