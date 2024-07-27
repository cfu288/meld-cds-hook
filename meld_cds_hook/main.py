from fastapi import FastAPI
from typing import Any, Dict, Optional, TypedDict, List
from pydantic import field_validator, BaseModel, HttpUrl
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
from math import log
from datetime import datetime
from pydantic import BaseModel, ValidationError
import requests
import asyncio
import aiohttp
from meld_cds_hook.models.meld_score_params import MeldScoreParams

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


async def get_patient_data(
    fhir_server: str, patient_id: str, bearer: Optional[str]
) -> tuple[str, str]:
    url = f"{fhir_server}/Patient/{patient_id}"
    print(url)
    headers = {}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            patient_data = await response.json()
            print(patient_data)
            if not patient_data:
                raise ValueError(f"No patient data found for patient ID {patient_id}.")
            sex = patient_data.get("gender", "")
            dob = patient_data.get("birthDate", "")
            return sex, dob


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
    meld_score = None
    meld_score_without_dialysis = None
    calculation_success = False
    calculation_errors = []

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
                get_patient_data(request.fhirServer, patientId, accessToken),
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

            if not isinstance(results[4], Exception):
                sex, dob = results[5]
                print(f"Patient sex: {sex}, DOB: {dob}")
            else:
                print(f"Error fetching patient data: {results[5]}")

        except Exception as e:
            print(f"Error in fetching observation values: {e}")
    else:
        print("FHIR server or patient ID not provided in the request.")


    try:
        response = calculate_meld_score(
            MeldScoreParams(
                sex=sex,
                bilirubin=bilirubin_value,
                sodium=sodium_value,
                inr=inr_value,
                albumin=albumin_value,
                creatinine=creatinine_value,
                had_dialysis=True,
                dob=dob,
            )
        )
        calculation_success = response["success"]
        if calculation_success:
            meld_score = response["value"]
            meld_score_without_dialysis = calculate_meld_score(
                MeldScoreParams(
                    sex=sex,
                    bilirubin=bilirubin_value,
                    sodium=sodium_value,
                    inr=inr_value,
                    albumin=albumin_value,
                    creatinine=creatinine_value,
                    had_dialysis=False,
                    dob=dob,
                )
            )["value"]
        else:
            calculation_errors = response["errors"]
            print(f"Error calculating MELD score: {response['errors']}")
    except ValidationError as e:
        # set calculation errors
        calculation_errors = [error['msg'] for error in e.errors()]
        print(f"Validation error calculating MELD score: {e}")

    detail_markdown = generate_detail_markdown(
        calculation_success, meld_score, meld_score_without_dialysis, calculation_errors,
        bilirubin_value, bilirubin_date, sodium_value, sodium_date, inr_value, inr_date,
        albumin_value, albumin_date, creatinine_value, creatinine_date, sex, dob
    )

    return {
        "cards": [
            {
                "uuid": uuid4(),
                "summary": f"MELD Score",
                "indicator": "info",
                "detail": detail_markdown,
                "source": {
                    "label": "OPTN",
                    "url": "https://optn.transplant.hrsa.gov/data/allocation-calculators/meld-calculator/",
                },
                "indicator": "info",
            }
        ]
    }


def generate_detail_markdown(
    calculation_success, meld_score, meld_score_without_dialysis, calculation_errors,
    bilirubin_value, bilirubin_date, sodium_value, sodium_date, inr_value, inr_date,
    albumin_value, albumin_date, creatinine_value, creatinine_date, sex, dob
):
    markdown_error_list = "".join(
        [f"- {error}\n" for error in calculation_errors] if calculation_errors else []
    )
    markdown_score_string = (
        f"Score with dialysis: **{meld_score}**; w/o dialysis: **{meld_score_without_dialysis}**"
        if calculation_success
        else "Score: Not calculated."
    )

    return f"""{markdown_score_string}

Errors: \n
{markdown_error_list}

---

| Parameter   | Value   | Date   |
|-------------|---------|--------|
| Bilirubin   | {bilirubin_value if bilirubin_value != 0 else "Not found"} | {bilirubin_date if bilirubin_value != 0 else ""} |
| Sodium      | {sodium_value if sodium_value != 0 else "Not found"}    | {sodium_date if sodium_value != 0 else ""}    |
| INR         | {inr_value if inr_value != 0 else "Not found"}       | {inr_date if inr_value != 0 else ""}       |
| Albumin     | {albumin_value if albumin_value != 0 else "Not found"}   | {albumin_date if albumin_value != 0 else ""}   |
| Creatinine  | {creatinine_value if creatinine_value != 0 else "Not found"}| {creatinine_date if creatinine_value != 0 else ""}|
| Sex         | {sex}             |                  |
| DOB         | {dob}             |                  |
"""

class MeldScoreResponse(TypedDict):
    value: Optional[float]
    errors: List[str]
    success: bool


def calculate_meld_score(params: MeldScoreParams) -> MeldScoreResponse:
    response: MeldScoreResponse = {"value": None, "errors": [], "success": False}
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
            response["errors"].append(
                "Age must be 12 or older to calculate MELD score."
            )
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
        response["value"] = meld_score
        response["success"] = True
        return response
    except ValidationError as e:
        error_message = f"Validation error calculating MELD score: {e}"
        print(error_message)
        response["errors"].append(error_message)
        return response
    except Exception as e:
        error_message = f"Error calculating MELD score: {e}"
        print(error_message)
        response["errors"].append(error_message)
        return response
