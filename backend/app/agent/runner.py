import json
import logging
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request as HttpRequest, urlopen

from pydantic import BaseModel, Field, StrictInt, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.prompts import SYSTEM_INSTRUCTION, TOOL_DECLARATIONS
from app.core.config import settings
from app.models.entities import CapacityRequest, Rack, RequestStatus
from app.services.placement import RackCapacity, best_fit

logger = logging.getLogger(__name__)


class AgentSummary(BaseModel):
    summary: str = Field(min_length=10, max_length=500)


class ToolAllocation(BaseModel):
    rack_id: StrictInt
    quantity: StrictInt


class ProposeToolArgs(BaseModel):
    request_id: StrictInt
    allocations: list[ToolAllocation]


def _placement(db: Session, request_id: int) -> list[dict[str, int]] | None:
    request = db.get(CapacityRequest, request_id)
    if request is None or request.status != RequestStatus.PENDING:
        raise ValueError("The request is not available for proposal")
    racks = db.scalars(select(Rack).where(Rack.site_id == request.site_id).order_by(Rack.id)).all()
    result = best_fit(request.quantity, [RackCapacity(rack.id, rack.total_slots-rack.used_slots) for rack in racks])
    if result is None:
        return None
    return [{"rack_id": item.rack_id, "quantity": item.quantity} for item in result]


def _run_local_tool(name: str, args: dict, db: Session, request: CapacityRequest, expected: list[dict[str, int]]) -> dict:
    if name == "get_site_capacity":
        if type(args.get("site_id")) is not int or args.get("site_id") != request.site_id:
            raise ValueError("Site is outside this request scope")
        racks = db.scalars(select(Rack).where(Rack.site_id == request.site_id)).all()
        return {"site_id": request.site_id, "total_slots": sum(r.total_slots for r in racks), "used_slots": sum(r.used_slots for r in racks), "available_slots": sum(r.total_slots-r.used_slots for r in racks)}
    if name == "list_pending_requests":
        pending = db.scalars(select(CapacityRequest).where(CapacityRequest.status == RequestStatus.PENDING).order_by(CapacityRequest.created_at).limit(20)).all()
        return {"requests": [{"id": item.id, "site_id": item.site_id, "quantity": item.quantity} for item in pending]}
    if name == "find_best_placement":
        if type(args.get("request_id")) is not int or args.get("request_id") != request.id:
            raise ValueError("Request is outside this proposal scope")
        checked = _placement(db, request.id)
        if checked != expected:
            raise ValueError("Placement changed while the proposal was being prepared")
        return {"allocations": checked, "feasible": checked is not None}
    if name == "propose_action":
        parsed = ProposeToolArgs.model_validate(args)
        submitted = [item.model_dump() for item in parsed.allocations]
        if parsed.request_id != request.id or submitted != expected:
            raise ValueError("Proposal did not match the validated placement")
        return {"status": "PENDING_HUMAN_REVIEW", "executed": False, "allocations": expected}
    raise ValueError("Tool is not allowed")


def _call_gemini(db: Session, request: CapacityRequest, expected: list[dict[str, int]]) -> str:
    model = settings.gemini_model
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    history = [{"role": "user", "parts": [{"text": json.dumps({"request_id": request.id, "site_id": request.site_id, "quantity": request.quantity, "description_untrusted": request.description})}]}]
    for _ in range(4):
        body = {"systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]}, "contents": history, "tools": [{"functionDeclarations": TOOL_DECLARATIONS}], "generationConfig": {"temperature": 0.1}}
        response_json = None
        for attempt in range(2):
            try:
                req = HttpRequest(endpoint, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": settings.gemini_api_key or ""}, method="POST")
                with urlopen(req, timeout=8) as response:
                    response_json = json.loads(response.read())
                break
            except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                if attempt == 1:
                    raise RuntimeError("Gemini request failed") from exc
                time.sleep(0.25 * (2 ** attempt))
        if not response_json or not response_json.get("candidates"):
            raise RuntimeError("Gemini returned no candidate")
        content = response_json["candidates"][0]["content"]
        calls = [part["functionCall"] for part in content.get("parts", []) if "functionCall" in part]
        if not calls:
            text = "".join(part.get("text", "") for part in content.get("parts", []))
            try:
                return AgentSummary.model_validate_json(text).summary
            except ValidationError:
                raise RuntimeError("Gemini response did not match the summary schema")
        history.append(content)
        for call in calls:
            result = _run_local_tool(call["name"], call.get("args", {}), db, request, expected)
            history.append({"role": "user", "parts": [{"functionResponse": {"name": call["name"], "response": result}}]})
    raise RuntimeError("Gemini exceeded the function-call limit")


def recommendation_summary(db: Session, request: CapacityRequest, allocations: list[dict[str, int]]) -> str:
    fallback = f"Place {request.quantity} servers across {len(allocations)} rack(s), subject to human approval."
    if not settings.gemini_api_key:
        return fallback
    try:
        return AgentSummary(summary=_call_gemini(db, request, allocations)).summary
    except Exception as exc:
        logger.warning("Gemini proposal summary failed; using safe fallback (%s)", type(exc).__name__)
        return fallback
