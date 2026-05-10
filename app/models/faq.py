"""FAQ 관련 Pydantic v2 모델."""

from enum import StrEnum
from pydantic import BaseModel, Field


class FAQCategory(StrEnum):
    GENERAL = "GENERAL"
    PATENT = "PATENT"
    INSPECTION = "INSPECTION"
    IMPORT_EXPORT = "IMPORT_EXPORT"
    EXHIBITION = "EXHIBITION"
    SALES = "SALES"
    SAMPLE = "SAMPLE"
    FOOD_TASTING = "FOOD_TASTING"
    DOCUMENTS = "DOCUMENTS"
    PENALTIES = "PENALTIES"
    PATENT_INFRINGEMENT = "PATENT_INFRINGEMENT"
    CONTACT = "CONTACT"
    LICENSE = "LICENSE"
    UNKNOWN = "UNKNOWN"


class FAQItem(BaseModel):
    id: str
    category: FAQCategory = FAQCategory.UNKNOWN
    question: str
    answer: str
    legal_basis: list[str] = Field(default_factory=list)
    notes: str = ""
    keywords: list[str] = Field(default_factory=list)
