from typing import Optional
import asyncio
import aiohttp
from dataclasses import dataclass


@dataclass
class MeldParamsUnverified:
    bilirubin_value: float = 0
    bilirubin_date: str = ""
    sodium_value: float = 0
    sodium_date: str = ""
    inr_value: float = 0
    inr_date: str = ""
    albumin_value: float = 0
    albumin_date: str = ""
    creatinine_value: float = 0
    creatinine_date: str = ""
    sex: str = ""
    dob: str = ""


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


async def fetch_meld_params(
    fhir_server: str, patient_id: str, bearer: Optional[str]
) -> MeldParamsUnverified:
    LAB_LOINC_CODES = {
        "total_bilirubin": "1975-2",
        "sodium": "2947-0",
        "inr": "34714-6",
        "albumin": "1751-7",
        "creatinine": "2160-0",
    }
    try:
        tasks = [
            get_latest_observation_value(
                fhir_server, patient_id, LAB_LOINC_CODES.get("total_bilirubin"), bearer
            ),
            get_latest_observation_value(
                fhir_server, patient_id, LAB_LOINC_CODES.get("sodium"), bearer
            ),
            get_latest_observation_value(
                fhir_server, patient_id, LAB_LOINC_CODES.get("inr"), bearer
            ),
            get_latest_observation_value(
                fhir_server, patient_id, LAB_LOINC_CODES.get("albumin"), bearer
            ),
            get_latest_observation_value(
                fhir_server, patient_id, LAB_LOINC_CODES.get("creatinine"), bearer
            ),
            get_patient_data(fhir_server, patient_id, bearer),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        meld_params = MeldParamsUnverified()

        if not isinstance(results[0], Exception):
            meld_params.bilirubin_value = results[0][0]
            meld_params.bilirubin_date = results[0][1]
        else:
            print(f"Error fetching Bilirubin value: {results[0]}")

        if not isinstance(results[1], Exception):
            meld_params.sodium_value = results[1][0]
            meld_params.sodium_date = results[1][1]
        else:
            print(f"Error fetching Sodium value: {results[1]}")

        if not isinstance(results[2], Exception):
            meld_params.inr_value = results[2][0]
            meld_params.inr_date = results[2][1]
        else:
            print(f"Error fetching INR value: {results[2]}")

        if not isinstance(results[3], Exception):
            meld_params.albumin_value = results[3][0]
            meld_params.albumin_date = results[3][1]
        else:
            print(f"Error fetching Albumin value: {results[3]}")

        if not isinstance(results[4], Exception):
            meld_params.creatinine_value = results[4][0]
            meld_params.creatinine_date = results[4][1]
        else:
            print(f"Error fetching Creatinine value: {results[4]}")

        if not isinstance(results[5], Exception):
            meld_params.sex = results[5][0]
            meld_params.dob = results[5][1]
        else:
            print(f"Error fetching patient data: {results[5]}")

        return meld_params

    except Exception as e:
        print(f"Error in fetching observation values: {e}")
        return MeldParamsUnverified()
