from datetime import date

from pydantic import BaseModel, Field


class ProposalCreate(BaseModel):
    order_id: int
    option_type: str
    source_ref: str
    quantity: int = Field(gt=0)
    expected_arrival: date
    actor: str = Field(min_length=2, max_length=100)
    rationale: str = Field(min_length=3, max_length=500)


class ApprovalRequest(BaseModel):
    actor: str = Field(min_length=2, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=100)
