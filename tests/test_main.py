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
        dob=datetime(1990, 1, 1),
    )
    score = calculate_meld_score(params)
    assert score is not None
    assert score == 14  # Expected MELD score based on provided values


def test_calculate_meld_score_age_15():
    params = MeldScoreParams(
        sex="male",
        bilirubin=1.2,
        sodium=135,
        inr=1.1,
        albumin=3.0,
        creatinine=1.5,
        had_dialysis=False,
        dob=datetime(datetime.today().year - 15, 1, 1),
    )
    score = calculate_meld_score(params)
    assert score is not None
    # Expected MELD score for age 15 based on provided values
    assert score == 16


def test_bilirubin_validation():
    with pytest.raises(ValueError, match="bilirubin must be between 0 and 99 mg/dL"):
        MeldScoreParams(
            sex="male",
            bilirubin=100,  # Invalid value
            sodium=135,
            inr=1.1,
            albumin=3.0,
            creatinine=1.5,
            had_dialysis=False,
            dob=datetime(1990, 1, 1),
        )


def test_sodium_validation():
    with pytest.raises(ValueError, match="sodium must be between 100 and 200 mEq/L"):
        MeldScoreParams(
            sex="male",
            bilirubin=1.2,
            sodium=99,  # Invalid value
            inr=1.1,
            albumin=3.0,
            creatinine=1.5,
            had_dialysis=False,
            dob=datetime(1990, 1, 1),
        )


def test_inr_validation():
    with pytest.raises(ValueError, match="INR must be between 0.5 and 99"):
        MeldScoreParams(
            sex="male",
            bilirubin=1.2,
            sodium=135,
            inr=0.4,  # Invalid value
            albumin=3.0,
            creatinine=1.5,
            had_dialysis=False,
            dob=datetime(1990, 1, 1),
        )


def test_creatinine_validation():
    with pytest.raises(
        ValueError, match="creatinine must be between 0.01 and 40 mg/dL"
    ):
        MeldScoreParams(
            sex="male",
            bilirubin=1.2,
            sodium=135,
            inr=1.1,
            albumin=3.0,
            creatinine=0,  # Invalid value
            had_dialysis=False,
            dob=datetime(1990, 1, 1),
        )


def test_albumin_validation():
    with pytest.raises(ValueError, match="albumin must be between 0.5 and 9.9 g/dL"):
        MeldScoreParams(
            sex="male",
            bilirubin=1.2,
            sodium=135,
            inr=1.1,
            albumin=0.4,  # Invalid value
            creatinine=1.5,
            had_dialysis=False,
            dob=datetime(1990, 1, 1),
        )


def test_sex_validation():
    with pytest.raises(ValueError, match='sex must be either "male" or "female"'):
        MeldScoreParams(
            sex="unknown",  # Invalid value
            bilirubin=1.2,
            sodium=135,
            inr=1.1,
            albumin=3.0,
            creatinine=1.5,
            had_dialysis=False,
            dob=datetime(1990, 1, 1),
        )

    # Valid values should not raise an exception
    try:
        MeldScoreParams(
            sex="male",
            bilirubin=1.2,
            sodium=135,
            inr=1.1,
            albumin=3.0,
            creatinine=1.5,
            had_dialysis=False,
            dob=datetime(1990, 1, 1),
        )
        MeldScoreParams(
            sex="female",
            bilirubin=1.2,
            sodium=135,
            inr=1.1,
            albumin=3.0,
            creatinine=1.5,
            had_dialysis=False,
            dob=datetime(1990, 1, 1),
        )
    except ValueError:
        pytest.fail("Unexpected ValueError for valid sex values")


def test_dob_validation():
    # Invalid date of birth (future date)
    with pytest.raises(ValueError):
        MeldScoreParams(
            sex="male",
            bilirubin=1.2,
            sodium=135,
            inr=1.1,
            albumin=3.0,
            creatinine=1.5,
            had_dialysis=False,
            dob=datetime(3000, 1, 1),  # Invalid value
        )

    # Valid date of birth (past date)
    try:
        MeldScoreParams(
            sex="male",
            bilirubin=1.2,
            sodium=135,
            inr=1.1,
            albumin=3.0,
            creatinine=1.5,
            had_dialysis=False,
            dob=datetime(1990, 1, 1),  # Valid value
        )
    except ValueError:
        pytest.fail("Unexpected ValueError for valid date of birth")
