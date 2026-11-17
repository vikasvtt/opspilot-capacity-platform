from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass


@dataclass(frozen=True)
class RackCapacity:
    rack_id: int
    available_slots: int


@dataclass(frozen=True)
class RackAllocation:
    rack_id: int
    quantity: int


def best_fit(quantity: int, racks: list[RackCapacity]) -> list[RackAllocation] | None:
    """Return a tight single-rack fit, or split across the largest racks.

    Sorting dominates the work: O(r log r) time and O(r) space for r racks.
    """
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    remaining = sorted((rack.available_slots, rack.rack_id) for rack in racks if rack.available_slots > 0)
    if sum(capacity for capacity, _ in remaining) < quantity:
        return None

    # Sorted capacities let us find the smallest rack that can hold the full request.
    fitting_index = bisect_left(remaining, (quantity, -1))
    if fitting_index < len(remaining):
        _, rack_id = remaining[fitting_index]
        return [RackAllocation(rack_id, quantity)]

    # No rack fits alone, so take the largest capacities first. Lower IDs break ties.
    allocations: list[RackAllocation] = []
    needed = quantity
    for capacity, rack_id in sorted(remaining, key=lambda item: (-item[0], item[1])):
        amount = min(capacity, needed)
        allocations.append(RackAllocation(rack_id, amount))
        needed -= amount
        if needed == 0:
            break
    return allocations
