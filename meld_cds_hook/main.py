from fastapi import FastAPI
from typing import Any, Dict, Optional
from pydantic import field_validator, BaseModel, HttpUrl
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
from math import log
from datetime import datetime
from pydantic import BaseModel, ValidationError
import requests
import asyncio
import aiohttp

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


async def get_latest_observation_value(
    fhir_server: str, patient_id: str, loinc_code: str, bearer: Optional[str]
) -> Optional[tuple[float, str]]:
    url = f"{fhir_server}/Observation?patient={patient_id}&code={loinc_code}&_sort:desc=date&_count=1"
    headers = {}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            observations = (await response.json()).get("entry", [])
            if not observations:
                raise ValueError(
                    f"No observations found for LOINC code {loinc_code} for the patient."
                )

            value = observations[0]["resource"]["valueQuantity"]["value"]
            date = observations[0]["resource"]["effectiveDateTime"]
            return float(value), date


@app.post("/cds-services/meld-score-optn")
async def meld_optn_hook(request: HookRequest):
    LAB_LOINC_CODES = {
        "total_bilirubin": "1975-2",
        "sodium": "2947-0",
        "inr": "34714-6",
        "albumin": "1751-7",
        "creatinine": "2160-0",
    }
    patientId = request.context.get("patientId")
    accessToken = (
        request.fhirAuthorization.get("access_token")
        if request.fhirAuthorization
        else None
    )

    # set default values
    bilirubin_value, bilirubin_date = 0, ""
    sodium_value, sodium_date = 0, ""
    inr_value, inr_date = 0, ""
    albumin_value, albumin_date = 0, ""
    creatinine_value, creatinine_date = 0, ""
    had_dialysis = False
    sex = ""
    dob = ""

    if request.fhirServer and patientId:
        try:
            tasks = [
                get_latest_observation_value(
                    request.fhirServer, patientId, "1975-2", accessToken
                ),
                get_latest_observation_value(
                    request.fhirServer,
                    patientId,
                    LAB_LOINC_CODES.get("sodium"),
                    accessToken,
                ),
                get_latest_observation_value(
                    request.fhirServer,
                    patientId,
                    LAB_LOINC_CODES.get("inr"),
                    accessToken,
                ),
                get_latest_observation_value(
                    request.fhirServer,
                    patientId,
                    LAB_LOINC_CODES.get("albumin"),
                    accessToken,
                ),
                get_latest_observation_value(
                    request.fhirServer,
                    patientId,
                    LAB_LOINC_CODES.get("creatinine"),
                    accessToken,
                ),
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            if not isinstance(results[0], Exception):
                bilirubin_value, bilirubin_date = results[0]
                print(f"Bilirubin value: {bilirubin_value}")
            else:
                print(f"Error fetching Bilirubin value: {results[0]}")

            if not isinstance(results[1], Exception):
                sodium_value, sodium_date = results[1]
                print(f"Sodium value: {sodium_value}")
            else:
                print(f"Error fetching Sodium value: {results[1]}")

            if not isinstance(results[2], Exception):
                inr_value, inr_date = results[2]
                print(f"INR value: {inr_value}")
            else:
                print(f"Error fetching INR value: {results[2]}")

            if not isinstance(results[3], Exception):
                albumin_value, albumin_date = results[3]
                print(f"Albumin value: {albumin_value}")
            else:
                print(f"Error fetching Albumin value: {results[3]}")

            if not isinstance(results[4], Exception):
                creatinine_value, creatinine_date = results[4]
                print(f"Creatinine value: {creatinine_value}")
            else:
                print(f"Error fetching Creatinine value: {results[4]}")

        except Exception as e:
            print(f"Error in fetching observation values: {e}")
    else:
        print("FHIR server or patient ID not provided in the request.")

    meld_score = None
    try:
        meld_score = calculate_meld_score(
            MeldScoreParams(
                sex=sex,
                bilirubin=bilirubin_value,
                sodium=sodium_value,
                inr=inr_value,
                albumin=albumin_value,
                creatinine=creatinine_value,
                had_dialysis=had_dialysis,
                dob=dob,
            )
        )
    except ValidationError as e:
        print(f"Validation error calculating MELD score: {e}")
        meld_score = None

    return {
        "cards": [
            {
                "uuid": uuid4(),
                "summary": f"MELD Score: {meld_score if meld_score is not None else 'Not calculated'}",
                "indicator": "info",
                "detail": f"""
| Parameter   | Value   | Date   |
|-------------|---------|--------|
| Bilirubin   | {bilirubin_value if bilirubin_value != 0 else "Not found"} | {bilirubin_date if bilirubin_value != 0 else ""} |
| Sodium      | {sodium_value if sodium_value != 0 else "Not found"}    | {sodium_date if sodium_value != 0 else ""}    |
| INR         | {inr_value if inr_value != 0 else "Not found"}       | {inr_date if inr_value != 0 else ""}       |
| Albumin     | {albumin_value if albumin_value != 0 else "Not found"}   | {albumin_date if albumin_value != 0 else ""}   |
| Creatinine  | {creatinine_value if creatinine_value != 0 else "Not found"}| {creatinine_date if creatinine_value != 0 else ""}|
| Had Dialysis| {had_dialysis}    |                  |
| Sex         | {sex}             |                  |
| DOB         | {dob}             |                  |
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

    @field_validator("dob")
    @classmethod
    def validate_dob(cls, v):
        if v > datetime.now():
            raise ValueError("dob must be less than or equal to the current date")
        return v

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, v):
        if v.lower() not in ["male", "female"]:
            raise ValueError('sex must be either "male" or "female"')
        return v

    @field_validator("bilirubin")
    @classmethod
    def validate_bilirubin(cls, v):
        if not (0 <= v <= 99):
            raise ValueError("bilirubin must be between 0 and 99 mg/dL")
        return v

    @field_validator("sodium")
    @classmethod
    def validate_sodium(cls, v):
        if not (100 <= v <= 200):
            raise ValueError("sodium must be between 100 and 200 mEq/L")
        return v

    @field_validator("inr")
    @classmethod
    def validate_inr(cls, v):
        if not (0.5 <= v <= 99):
            raise ValueError("INR must be between 0.5 and 99")
        return v

    @field_validator("albumin")
    @classmethod
    def validate_albumin(cls, v):
        if not (0.5 <= v <= 9.9):
            raise ValueError("albumin must be between 0.5 and 9.9 g/dL")
        return v

    @field_validator("creatinine")
    @classmethod
    def validate_creatinine(cls, v):
        if not (0.01 <= v <= 40):
            raise ValueError("creatinine must be between 0.01 and 40 mg/dL")
        return v


def calculate_meld_score(params: MeldScoreParams) -> Optional[float]:
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
        return meld_score
    except ValidationError as e:
        print(f"Validation error calculating MELD score: {e}")
        return None
    except Exception as e:
        print(f"Error calculating MELD score: {e}")
        return None
