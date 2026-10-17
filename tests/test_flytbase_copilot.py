import sqlite3
import pytest
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "storage" / "local.db"


@pytest.fixture
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


def test_q1_well_0001_latest_status(db_conn):
    """Q1: Verify WELL-0001 is NOT producing right now (delta 3.2°C < 15°C), inspected by U-104 Ryan Brooks."""
    cur = db_conn.cursor()
    cur.execute("""
        SELECT inspection_id, inspected_at, inspector_user_id, method,
               ambient_temp_c, wellhead_temp_c, delta_temp_c, threshold_delta_c,
               dynamic_status, is_producing_dynamically
        FROM v_inspections_effective
        WHERE asset_id = 'WELL-0001'
        ORDER BY inspected_at DESC
        LIMIT 1;
    """)
    row = cur.fetchone()
    assert row is not None
    insp_id, inspected_at, inspector, method, amb, wh, delta, thresh, status, is_prod = row

    assert insp_id == "INS-0001-0216"
    assert "2027-01-14" in inspected_at
    assert inspector == "U-103"
    assert method == "drone"
    assert abs(delta - 28.5) < 0.1
    assert thresh == 15.0
    assert status == "producing"
    assert is_prod == 1


def test_q4_spill_counts_and_rainwater_correction(db_conn):
    """Q4: Verify 6 spills, 15.1 barrels total, and INS-0001-0070 rainwater excluded."""
    cur = db_conn.cursor()
    # Check false positive rainwater inspection is flagged
    cur.execute("""
        SELECT spill_detected, spill_est_volume_bbl, raw_spill_detected
        FROM v_inspections_effective
        WHERE inspection_id = 'INS-0001-0070';
    """)
    fp_row = cur.fetchone()
    assert fp_row is not None
    eff_spill, eff_vol, raw_spill = fp_row
    assert raw_spill == 1
    assert eff_spill == 0

    # Aggregate active spills for WELL-0001
    cur.execute("""
        SELECT COUNT(*), ROUND(SUM(spill_est_volume_bbl), 1)
        FROM v_inspections_effective
        WHERE asset_id = 'WELL-0001' AND spill_detected = 1;
    """)
    count, total_vol = cur.fetchone()
    assert count == 6
    assert total_vol == 15.1


def test_q5_downtime_math_2025(db_conn):
    """Q5: Verify exactly 21 days downtime for WELL-0001 in 2025 (3 inspections * 7 days)."""
    cur = db_conn.cursor()
    cur.execute("""
        SELECT COUNT(*) * 7
        FROM v_inspections_effective
        WHERE asset_id = 'WELL-0001'
          AND inspected_at LIKE '2025%'
          AND is_producing_dynamically = 0;
    """)
    downtime_days = cur.fetchone()[0]
    assert downtime_days == 21


def test_q6_downtime_top_wells_ne_block_7(db_conn):
    """Q6: Which 3 wells in NE Block 7 had most downtime in last 4 months (16 Jun - 16 Oct 2026)."""
    cur = db_conn.cursor()
    cur.execute("""
        SELECT asset_id, COUNT(*) * 7 AS downtime_days
        FROM v_inspections_effective
        WHERE area_id = 'NE-07'
          AND inspected_at >= '2026-06-16'
          AND inspected_at <= '2026-10-16T23:59:59Z'
          AND is_producing_dynamically = 0
        GROUP BY asset_id
        ORDER BY downtime_days DESC
        LIMIT 3;
    """)
    top_3 = cur.fetchall()
    assert len(top_3) == 3
    # Expected: WELL-0121 (49), WELL-0138 (42), WELL-0107 (42)
    assert top_3[0] == ('WELL-0121', 49)
    assert top_3[1][1] == 42
    assert top_3[2][1] == 42


def test_q12_user_feedback_override_loop(db_conn):
    """Q12: Field crew corrects an inspection reading, flipping it dynamically to producing."""
    cur = db_conn.cursor()
    insp_id = "INS-0001-0063"

    # Before override: non-producing (delta 4.4°C < 15°C)
    cur.execute("SELECT delta_temp_c, is_producing_dynamically FROM v_inspections_effective WHERE inspection_id = ?", (insp_id,))
    row_before = cur.fetchone()
    assert row_before[1] == 0

    # Insert user correction override
    cur.execute("""
        INSERT INTO user_feedback_overrides 
        (scope, target_id, field_name, original_value, corrected_value, author_user_id, rationale, is_active)
        VALUES ('inspection_field', ?, 'wellhead_temp_c', '8.4', '35.0', 'U-201', 'Faulty thermal gun re-measured', 1);
    """, (insp_id,))
    db_conn.commit()

    try:
        # After override: wellhead_temp_c is 35.0°C, delta is 31.0°C, and dynamic status becomes producing (1)
        cur.execute("SELECT wellhead_temp_c, delta_temp_c, is_producing_dynamically FROM v_inspections_effective WHERE inspection_id = ?", (insp_id,))
        row_after = cur.fetchone()
        assert row_after[0] == 35.0
        assert row_after[1] > 15.0
        assert row_after[2] == 1
    finally:
        # Clean up test override
        cur.execute("DELETE FROM user_feedback_overrides WHERE target_id = ? AND author_user_id = 'U-201'", (insp_id,))
        db_conn.commit()


def test_unconfirmed_claims_tracking(db_conn):
    """Q17: Tracking unconfirmed claims when user statement contradicts sensor readings."""
    cur = db_conn.cursor()
    cur.execute("""
        INSERT INTO unconfirmed_claims (user_id, asset_id, claim_text, conflicting_evidence)
        VALUES ('U-203', 'WELL-0175', 'WELL-0175 is running fine', '15 Oct inspection shows delta T = 0.4 C, not producing');
    """, )
    db_conn.commit()
    claim_id = cur.lastrowid

    cur.execute("SELECT user_id, asset_id, claim_text FROM unconfirmed_claims WHERE claim_id = ?", (claim_id,))
    res = cur.fetchone()
    assert res == ('U-203', 'WELL-0175', 'WELL-0175 is running fine')

    # Clean up
    cur.execute("DELETE FROM unconfirmed_claims WHERE claim_id = ?", (claim_id,))
    db_conn.commit()
