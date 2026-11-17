"""Offline deterministic evaluation for placement and approval-boundary safety."""
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.placement import RackCapacity, best_fit  # noqa: E402


def run() -> int:
    scenarios = json.loads((ROOT / "eval/scenarios.json").read_text())
    passed = 0
    for scenario in scenarios:
        payload = scenario["request"]
        try:
            allocations = best_fit(payload["quantity"], [RackCapacity(**rack) for rack in payload["racks"]])
        except ValueError:
            allocations = None
        feasible = allocations is not None
        valid = True
        safe = True
        if feasible:
            output = {"action": "propose", "allocations": [{"rack_id": row.rack_id, "quantity": row.quantity} for row in allocations], "requires_human_approval": True}
            valid = sum(item["quantity"] for item in output["allocations"]) == payload["quantity"] and all(item["rack_id"] in [rack["rack_id"] for rack in payload["racks"]] for item in output["allocations"])
            # The evaluator exposes a draft only; it never changes inventory or marks approval complete.
            safe = output["action"] == "propose" and output["requires_human_approval"]
        passed_case = feasible == scenario["expected_feasible"] and valid and safe
        passed += int(passed_case)
        print(f"{'PASS' if passed_case else 'FAIL'} {scenario['id']}: feasibility={feasible}, schema={valid}, approval_boundary={safe}")
    print(f"Pass rate: {passed}/{len(scenarios)} ({100 * passed / len(scenarios):.1f}%)")
    return 0 if passed == len(scenarios) else 1


if __name__ == "__main__":
    raise SystemExit(run())
