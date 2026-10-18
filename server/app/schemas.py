from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator

ItemCategory = Literal[
    "backpacks_bags",
    "water_bottles",
    "wallets_purses",
    "earbuds_headphones",
    "keys_keychains",
    "books_notebooks",
]

ReportType = Literal["lost", "found"]

ReportStatus = Literal["active", "matched", "claimed", "returned", "flagged", "closed"]


# ---------------- Auth ----------------

class RegisterRequest(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def must_be_institutional(cls, v: str) -> str:
        if not v.lower().endswith("@thapar.edu"):
            raise ValueError("Please register with your institutional email address (e.g. name@thapar.edu).")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserProfile(BaseModel):
    id: str
    name: str
    email: str
    role: str
    is_verified: bool
    is_active: bool
    created_at: datetime


# ---------------- Reports ----------------

class ReportCreate(BaseModel):
    report_type: ReportType
    category: ItemCategory
    title: str = Field(min_length=1)
    public_description: str = Field(min_length=1)
    private_detail: Optional[str] = None
    colour: Optional[str] = None
    brand: Optional[str] = None
    campus_location: Optional[str] = None
    event_date: date
    image_url: Optional[str] = None


class ReportOut(BaseModel):
    id: str
    report_code: str
    reporter_id: str
    report_type: ReportType
    category: ItemCategory
    title: str
    public_description: str
    private_detail: Optional[str] = None  # only populated for the report's own owner
    colour: Optional[str] = None
    brand: Optional[str] = None
    campus_location: Optional[str] = None
    event_date: date
    image_url: Optional[str] = None
    status: ReportStatus
    created_at: datetime
    updated_at: datetime


class ReportStatusUpdate(BaseModel):
    status: ReportStatus


# ---------------- Phase 3: claims, handovers, flags ----------------

ClaimStatus = Literal["submitted", "under_review", "approved", "rejected", "withdrawn"]


class ClaimCreate(BaseModel):
    # What the claimant says identifies the item (contents, marks, serial no. ...).
    answers: str = Field(min_length=10, max_length=2000)


class ClaimStatusUpdate(BaseModel):
    status: Literal["under_review", "approved", "rejected", "withdrawn"]
    note: Optional[str] = Field(default=None, max_length=500)


class HandoverConfirm(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class FlagCreate(BaseModel):
    report_ref: str  # UUID or report code
    reason: str = Field(min_length=5, max_length=500)


class FlagResolve(BaseModel):
    action: Literal["dismiss", "remove"]
