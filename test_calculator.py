import numpy as np
import pytest

from gridfinity_calculator import compute_splits, build_plate_matrix, adjust_max_units_for_padding


# --- compute_splits ---

def test_splits_exact_multiple():
    assert compute_splits(10, 5) == [5, 5]

def test_splits_no_remainder():
    assert compute_splits(6, 6) == [6]

def test_splits_normal_remainder():
    # 11 = 5+5+1 → last chunk merges to give [5, 4, 2]
    assert compute_splits(11, 5) == [5, 4, 2]

def test_splits_remainder_2():
    # 12 = 5+5+2 → no merge needed
    assert compute_splits(12, 5) == [5, 5, 2]

def test_splits_single_chunk():
    assert compute_splits(3, 5) == [3]

def test_splits_total_equals_max():
    assert compute_splits(5, 5) == [5]

def test_splits_remainder_1_two_chunks():
    # 7 = 4+3 normally, but 4+4 max=4 → 4+3, last!=1 so no merge
    assert compute_splits(7, 4) == [4, 3]

def test_splits_no_one_unit_chunk():
    for total in range(1, 30):
        for max_chunk in range(2, 10):
            chunks = compute_splits(total, max_chunk)
            assert all(c >= 1 for c in chunks)
            assert sum(chunks) == total
            # A 1-unit final chunk is unavoidable when max_chunk==2 and remainder==1
            # (all preceding chunks are 2, so merging would just move the 1 to the front)
            unavoidable = (max_chunk == 2 and total % max_chunk == 1)
            if len(chunks) > 1 and not unavoidable:
                assert chunks[-1] != 1, f"1-unit chunk for total={total}, max={max_chunk}: {chunks}"


# --- build_plate_matrix helpers ---

def assert_matrix_valid(matrix, total_x, total_y, max_x, max_y):
    assert matrix.shape == (total_y, total_x), "Wrong matrix shape"

    unique = [p for p in np.unique(matrix) if p != 0]
    assert len(unique) > 0, "No plates assigned"

    # Every cell must belong to exactly one plate
    assert (matrix > 0).all(), "Some cells unassigned"

    for plate_id in unique:
        rows, cols = np.where(matrix == plate_id)

        # Plate must be a clean rectangle (no L-shapes / holes)
        min_r, max_r = rows.min(), rows.max()
        min_c, max_c = cols.min(), cols.max()
        expected_cells = (max_r - min_r + 1) * (max_c - min_c + 1)
        assert len(rows) == expected_cells, (
            f"Plate {plate_id} is not a rectangle: has {len(rows)} cells, "
            f"bounding box implies {expected_cells}"
        )

        plate_w = max_c - min_c + 1
        plate_h = max_r - min_r + 1

        # No plate should be 1-unit wide/tall when the split can avoid it.
        # A 1-unit plate is unavoidable when total % max == 1 and max == 2
        # (e.g. total=3, max=2 must produce [2,1] — no valid all->=2 split exists).
        x_avoidable = not (total_x % max_x == 1 and max_x == 2)
        y_avoidable = not (total_y % max_y == 1 and max_y == 2)
        if total_x > 1 and x_avoidable:
            assert plate_w >= 2, f"Plate {plate_id} has width=1"
        if total_y > 1 and y_avoidable:
            assert plate_h >= 2, f"Plate {plate_id} has height=1"

        # No plate should exceed the printer max
        assert plate_w <= max_x, f"Plate {plate_id} width {plate_w} exceeds max {max_x}"
        assert plate_h <= max_y, f"Plate {plate_id} height {plate_h} exceeds max {max_y}"


# --- build_plate_matrix ---

def test_exact_fit_single_plate():
    m, n = build_plate_matrix(5, 5, 6, 6)
    assert n == 1
    assert_matrix_valid(m, 5, 5, 6, 6)

def test_exact_multiple_2x2_plates():
    m, n = build_plate_matrix(10, 10, 5, 5)
    assert n == 4
    assert_matrix_valid(m, 10, 10, 5, 5)

def test_reported_bug_11x11_max5():
    # The original bug: both axes have a 1-unit remainder → overlapping plates
    m, n = build_plate_matrix(11, 11, 5, 5)
    assert_matrix_valid(m, 11, 11, 5, 5)

def test_remainder_x_only():
    m, n = build_plate_matrix(11, 10, 5, 5)
    assert_matrix_valid(m, 11, 10, 5, 5)

def test_remainder_y_only():
    m, n = build_plate_matrix(10, 11, 5, 5)
    assert_matrix_valid(m, 10, 11, 5, 5)

def test_single_row():
    m, n = build_plate_matrix(11, 1, 5, 5)
    assert_matrix_valid(m, 11, 1, 5, 5)

def test_single_column():
    m, n = build_plate_matrix(1, 11, 5, 5)
    assert_matrix_valid(m, 1, 11, 5, 5)

def test_large_grid():
    m, n = build_plate_matrix(23, 17, 6, 6)
    assert_matrix_valid(m, 23, 17, 6, 6)

# --- adjust_max_units_for_padding ---

def test_issue10_corner_justify_4x4_valid():
    # Issue #10: printer 180mm, space 324x231mm.
    # The old loop incorrectly reduced max from 4 to 3 because it checked
    # max_units*42 + leftover instead of the actual rightmost plate size.
    # compute_splits(7,4)=[4,3] → rightmost=3 → 3*42+30=156 ≤ 180, so 4x4 is valid.
    mx, my = adjust_max_units_for_padding(
        total_units_x=7, total_units_y=5,
        max_units_x=4, max_units_y=4,
        leftover_x=30, leftover_y=21,
        printer_x_mm=180, printer_y_mm=180,
        padding_option="Corner Justify"
    )
    assert mx == 4 and my == 4, f"Expected 4x4, got {mx}x{my}"

def test_corner_justify_reduces_when_truly_needed():
    # If the rightmost plate + padding genuinely doesn't fit, max must reduce.
    # compute_splits(6,4)=[4,2] → rightmost=2 → 2*42+41=125 ≤ 100? No.
    # Use a case where it really can't fit: leftover=50 (hypothetical large leftover).
    # compute_splits(4,4)=[4] → rightmost=4 → 4*42+50=218 > 200 → reduce to 3
    # compute_splits(4,3)=[3,1]→merge→[2,2] → rightmost=2 → 2*42+50=134 ≤ 200 ✓
    mx, my = adjust_max_units_for_padding(
        total_units_x=4, total_units_y=4,
        max_units_x=4, max_units_y=4,
        leftover_x=50, leftover_y=50,
        printer_x_mm=200, printer_y_mm=200,
        padding_option="Corner Justify"
    )
    # Rightmost plate after reduction must be padded to fit
    x_splits = compute_splits(4, mx)
    y_splits = compute_splits(4, my)
    assert x_splits[-1] * 42 + 50 <= 200
    assert y_splits[-1] * 42 + 50 <= 200

def test_center_justify_uses_largest_plate():
    # Center Justify: largest plate (first split) + half padding must fit.
    # compute_splits(10,5)=[5,5] → first=5 → 5*42+leftover/2 must fit.
    mx, my = adjust_max_units_for_padding(
        total_units_x=10, total_units_y=10,
        max_units_x=5, max_units_y=5,
        leftover_x=20, leftover_y=20,
        printer_x_mm=230, printer_y_mm=230,
        padding_option="Center Justify"
    )
    x_splits = compute_splits(10, mx)
    assert x_splits[0] * 42 + 20 / 2 <= 230

def test_no_unnecessary_reduction():
    # Sanity check: when plates already fit, max_units should not change.
    mx, my = adjust_max_units_for_padding(
        total_units_x=6, total_units_y=6,
        max_units_x=3, max_units_y=3,
        leftover_x=10, leftover_y=10,
        printer_x_mm=180, printer_y_mm=180,
        padding_option="Corner Justify"
    )
    assert mx == 3 and my == 3


def test_asymmetric_reduction():
    # Y needs reducing but X does not — the old loop would have reduced both,
    # leaving X smaller than necessary. The new function handles each axis independently.
    # X: compute_splits(6,3)=[3,3] → rightmost=3 → 3*42+5=131 ≤ 180 ✓ (no change needed)
    # Y: compute_splits(6,3)=[3,3] → topmost=3  → 3*42+60=186 > 180 ✗ (needs reduction)
    mx, my = adjust_max_units_for_padding(
        total_units_x=6, total_units_y=6,
        max_units_x=3, max_units_y=3,
        leftover_x=5, leftover_y=60,
        printer_x_mm=180, printer_y_mm=180,
        padding_option="Corner Justify"
    )
    assert mx == 3, f"X should stay at 3, got {mx}"
    assert my < 3, f"Y should have been reduced below 3, got {my}"

def test_center_justify_reduces_when_needed():
    # Center Justify: largest plate (= max_units) + half leftover must fit.
    # compute_splits(8,4)=[4,4] → first=4 → 4*42+40/2=188 > 170 → reduce to 3
    # compute_splits(8,3)=[3,3,2] → first=3 → 3*42+20=146 ≤ 170 ✓
    mx, my = adjust_max_units_for_padding(
        total_units_x=8, total_units_y=8,
        max_units_x=4, max_units_y=4,
        leftover_x=40, leftover_y=40,
        printer_x_mm=170, printer_y_mm=170,
        padding_option="Center Justify"
    )
    x_splits = compute_splits(8, mx)
    assert x_splits[0] * 42 + 40 / 2 <= 170, "Largest plate + half padding should fit"
    assert mx < 4, f"Max should have been reduced from 4, got {mx}"


def test_all_totals_and_maxes():
    # Exhaustively check a range of sizes — no manual input needed
    for total_x in range(1, 20):
        for total_y in range(1, 20):
            for max_size in range(2, 8):
                m, _ = build_plate_matrix(total_x, total_y, max_size, max_size)
                assert_matrix_valid(m, total_x, total_y, max_size, max_size)
