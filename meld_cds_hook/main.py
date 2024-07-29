from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
from pydantic import ValidationError
from meld_cds_hook.models.meld_score_params import MeldScoreParams
from meld_cds_hook.services.calculate_meld_score import calculate_meld_score
from meld_cds_hook.models.hook_request import HookRequest
from meld_cds_hook.services.fetch_meld_data import fetch_meld_data

app = FastAPI()


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
async def meld_optn_hook(request: HookRequest):
    patientId = request.context.get("patientId")
    accessToken = (
        request.fhirAuthorization.get("access_token")
        if request.fhirAuthorization
        else None
    )

    meld_score = None
    meld_score_without_dialysis = None
    calculation_success = False
    calculation_errors = []

    if request.fhirServer and patientId:
        meld_params = await fetch_meld_data(request.fhirServer, patientId, accessToken)
        bilirubin_value = meld_params.bilirubin_value
        bilirubin_date = meld_params.bilirubin_date
        sodium_value = meld_params.sodium_value
        sodium_date = meld_params.sodium_date
        inr_value = meld_params.inr_value
        inr_date = meld_params.inr_date
        albumin_value = meld_params.albumin_value
        albumin_date = meld_params.albumin_date
        creatinine_value = meld_params.creatinine_value
        creatinine_date = meld_params.creatinine_date
        sex = meld_params.sex
        dob = meld_params.dob

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
            calculation_errors = [error["msg"] for error in e.errors()]
            print(f"Validation error calculating MELD score: {e}")

        detail_markdown = generate_detail_markdown(
            calculation_success,
            meld_score,
            meld_score_without_dialysis,
            calculation_errors,
            bilirubin_value,
            bilirubin_date,
            sodium_value,
            sodium_date,
            inr_value,
            inr_date,
            albumin_value,
            albumin_date,
            creatinine_value,
            creatinine_date,
            sex,
            dob,
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
    else:
        print("FHIR server and patient ID are required.")
        return {"cards": []}


def generate_detail_markdown(
    calculation_success,
    meld_score,
    meld_score_without_dialysis,
    calculation_errors,
    bilirubin_value,
    bilirubin_date,
    sodium_value,
    sodium_date,
    inr_value,
    inr_date,
    albumin_value,
    albumin_date,
    creatinine_value,
    creatinine_date,
    sex,
    dob,
):
    markdown_error_list = "".join(
        [f"- {error}\n" for error in calculation_errors] if calculation_errors else []
    )
    markdown_score_string = (
        f"**Score with dialysis:** *{meld_score}*; **w/o dialysis:** *{meld_score_without_dialysis}*"
        if calculation_success
        else "**Score:** *Not calculated*"
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
