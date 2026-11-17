import pytest

from app.services.placement import RackCapacity, best_fit


def test_single_tight_fit_is_preferred():
    result = best_fit(6, [RackCapacity(1, 20), RackCapacity(2, 7)])
    assert [(row.rack_id, row.quantity) for row in result] == [(2, 6)]


def test_request_splits_across_racks_when_needed():
    result = best_fit(11, [RackCapacity(1, 6), RackCapacity(2, 5), RackCapacity(3, 3)])
    assert [(row.rack_id, row.quantity) for row in result] == [(1, 6), (2, 5)]


def test_equal_fits_use_lower_rack_id():
    assert best_fit(5, [RackCapacity(9, 5), RackCapacity(2, 5)])[0].rack_id == 2


def test_insufficient_capacity_has_no_placement():
    assert best_fit(7, [RackCapacity(1, 4), RackCapacity(2, 2)]) is None


def test_non_positive_request_is_rejected():
    with pytest.raises(ValueError):
        best_fit(0, [RackCapacity(1, 4)])
