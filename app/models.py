from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class Category(str, Enum):
    TRADE_IN = "trade_in"
    SERVICE = "service"
    OFFER_ONLY = "offer_only"
    OTHER = "other"


class Attachment(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    content_type: Optional[str] = None
    size: Optional[int] = None
    is_inline: bool = False
    content_bytes: Optional[str] = None  # base64-encoded innhold fra Graph


class EmailMessage(BaseModel):
    id: Optional[str] = None
    subject: Optional[str] = None
    body: str
    from_address: Optional[str] = None
    to_addresses: List[str] = []
    sent_at: Optional[str] = None
    attachments: List[Attachment] = []


class EmailThread(BaseModel):
    conversation_id: Optional[str] = None
    messages: List[EmailMessage]


class TradeInInfo(BaseModel):
    registration_number: Optional[str] = None
    odometer_km: Optional[str] = None
    service_history: Optional[str] = None
    has_pictures: bool = False
    general_condition: Optional[str] = None
    damages: Optional[str] = None
    tires_condition: Optional[str] = None


class ServiceType(str, Enum):
    SERVICE = "service"
    REPAIR = "repair"
    OTHER = "other"
    DAMAGE_INSPECTION = "damage_inspection"


class ServiceInfo(BaseModel):
    service_type: Optional[ServiceType] = None
    odometer_km: Optional[str] = None
    registration_number: Optional[str] = None
    damage_case_number: Optional[str] = None
    insurance_company: Optional[str] = None
    last_service_when: Optional[str] = None


class ClassificationResult(BaseModel):
    category: Category
    confidence: float


class RequirementsResult(BaseModel):
    complete: bool
    missing: List[str]
    desired_missing: List[str] = []


class ProcessThreadRequest(BaseModel):
    subject: Optional[str] = None
    body: str
    attachments: List[Attachment] = []


class ProcessThreadResponse(BaseModel):
    category: Category
    confidence: float
    trade_in_info: Optional[TradeInInfo] = None
    service_info: Optional[ServiceInfo] = None
    requirements: Optional[RequirementsResult] = None
    reply_draft: Optional[str] = None
    action: str

