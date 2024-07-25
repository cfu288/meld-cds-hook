from fastapi import FastAPI
from typing import Any, Dict, Optional
from pydantic import field_validator, BaseModel, HttpUrl
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
from math import log
from datetime import datetime
from pydantic import BaseModel, ValidationError

app = FastAPI()


class FhirAuthorization(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    scope: str
    subject: str


class Context(BaseModel):
    userId: str
    patientId: str
    encounterId: str


class HookRequest(BaseModel):
    hook: str
    hookInstance: str
    fhirServer: Optional[HttpUrl] = None
    fhirAuthorization: Optional[FhirAuthorization] = None
    context: Dict[str, Any]
    prefetch: Optional[Dict[str, Any]] = None


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/cds-services")
def read_root():
    return {
        "services": [
            {
                "hook": "patient-view",
                "title": "MELD Score (OPTN)",
                "description": "The Model for End-Stage Liver Disease (MELD) is a calculated formula used to assign priority to most liver transplant candidates age 12 and older based upon their medical urgency. Read more at https://optn.transplant.hrsa.gov/data/allocation-calculators/meld-calculator/",
                "id": "meld-score-optn",
            }
        ]
    }


@app.post("/cds-services/meld-score-optn")
def meld_optn_hook(request: HookRequest):
    return {
        "cards": [
            {
                "uuid": uuid4(),
                "summary": "MELD Score (OPTN): 15",
                "indicator": "info",
                "detail": f"""
| Parameter   | Value   | Date   |
|-------------|---------|--------|
| Sex         | male    | 01/24  |
| Bilirubin   | 1.2     | 01/24  |
| Sodium      | 135     | 01/24  |
| INR         | 1.1     | 01/24  |
| Albumin     | 3.0     | 01/24  |
| Creatinine  | 1.5     | 01/24  |
| Had Dialysis| False   | 01/24  |
| DOB         | 1990-01-01 | 01/24  |
""",
                "source": {
                    "label": "OPTN",
                    "url": "https://optn.transplant.hrsa.gov/data/allocation-calculators/meld-calculator/",
                },
                "indicator": "info",
            }
        ]
    }


# https://optn.transplant.hrsa.gov/media/qmsdjqst/meld-peld-calculator-user-guide.pdf
class MeldScoreParams(BaseModel):
    sex: str
    bilirubin: float
    sodium: float
    inr: float
    albumin: float
    creatinine: float
    had_dialysis: bool
    dob: datetime

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, v):
        if v.lower() not in ["male", "female"]:
            raise ValueError('sex must be either "male" or "female"')
        return v

    @field_validator("bilirubin", "sodium", "inr", "albumin", "creatinine")
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError("value must be positive")
        return v


def calculate_meld_score(params: MeldScoreParams) -> Optional[float]:
    try:
        # Calculate age
        today = datetime.today()
        age = today.year - params.dob.year - ((today.month, today.day) < (params.dob.month, params.dob.day))

        # Only calculate if age > 18
        if age <= 18:
            return None

        # Apply constraints to input values
        bilirubin = max(params.bilirubin, 1.0)
        inr = max(params.inr, 1.0)
        creatinine = max(params.creatinine, 1.0)
        sodium = min(max(params.sodium, 125), 137)
        albumin = min(max(params.albumin, 1.5), 3.5)

        # Adjust creatinine for dialysis conditions
        if creatinine > 3.0 or params.had_dialysis:
            creatinine = 3.0

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
        return meld_score
    except ValidationError as e:
        print(f"Validation error calculating MELD score: {e}")
        return None
    except Exception as e:
        print(f"Error calculating MELD score: {e}")
        return None

