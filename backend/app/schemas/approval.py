from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ProposalOutput(BaseModel):
    id: int
    request_id: int
    proposed_by: str
    proposal_json: dict
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ReviewInput(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    reason: str = Field(min_length=1, max_length=2000)
