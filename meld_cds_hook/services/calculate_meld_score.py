from typing import Optional, List
from math import log
from datetime import datetime
from pydantic import ValidationError
from meld_cds_hook.models.meld_score_params import MeldScoreParams
from dataclasses import dataclass, field


@dataclass
class MeldScoreCalculatedResult:
    value: Optional[float] = None
    errors: List[str] = field(default_factory=list)
    success: bool = False


def calculate_meld_score(params: MeldScoreParams) -> MeldScoreCalculatedResult:
    response = MeldScoreCalculatedResult()
    try:
        # Calculate age
        today = datetime.today()
        age = (
            today.year
            - params.dob.year
            - ((today.month, today.day) < (params.dob.month, params.dob.day))
        )

        # Only calculate if age >= 12
        if age < 12:
            response.errors.append("Age must be 12 or older to calculate MELD score.")
            return response

        # Apply constraints to input values
        bilirubin = max(params.bilirubin, 1.0)
        inr = max(params.inr, 1.0)
        creatinine = max(params.creatinine, 1.0)
        sodium = min(max(params.sodium, 125), 137)
        albumin = min(max(params.albumin, 1.5), 3.5)

        # Adjust creatinine for dialysis conditions
        if creatinine > 3.0 or params.had_dialysis:
            creatinine = 3.0

        if 12 <= age < 18:
            meld_score = (
                (4.56 * log(bilirubin))
                + (0.82 * (137 - sodium))
                - (0.24 * (137 - sodium) * log(bilirubin))
                + (9.09 * log(inr))
                + (11.14 * log(creatinine))
                + (1.85 * (3.5 - albumin))
                - (1.83 * (3.5 - albumin) * log(creatinine))
                + 7.33
            )
        else:
            meld_score = (
                (1.33 if params.sex.lower() == "female" else 0)
                + (4.56 * log(bilirubin))
                + (0.82 * (137 - sodium))
                - (0.24 * (137 - sodium) * log(bilirubin))
                + (9.09 * log(inr))
                + (11.14 * log(creatinine))
                + (1.85 * (3.5 - albumin))
                - (1.83 * (3.5 - albumin) * log(creatinine))
                + 6
            )

        # The minimum MELD score is 6, and the maximum MELD score is 40. Values above 40 are rounded to 40 in the OPTN system. The MELD score derived from this calculation is rounded to the nearest whole number.
        meld_score = round(meld_score)
        meld_score = min(max(meld_score, 6), 40)
        response.value = meld_score
        response.success = True
        return response
    except ValidationError as e:
        error_message = f"Validation error calculating MELD score: {e}"
        print(error_message)
        response.errors.append(error_message)
        return response
    except Exception as e:
        error_message = f"Error calculating MELD score: {e}"
        print(error_message)
        response.errors.append(error_message)
        return response
