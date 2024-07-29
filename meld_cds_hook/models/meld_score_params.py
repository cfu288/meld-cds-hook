from typing import Any, Dict, Optional, TypedDict, List
from pydantic import field_validator, BaseModel, HttpUrl
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
from math import log
from datetime import datetime
from pydantic import BaseModel, ValidationError


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
