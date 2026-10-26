import numpy as np
import pandas as pd

from app import detect_candidate_columns, prepare_analysis_data


def test_detect_candidate_columns_handles_common_aliases():
    df = pd.DataFrame(
        {
            "Current (A)": [1.0, 2.0],
            "Voltage (V)": [3.0, 4.0],
        }
    )

    current_col = detect_candidate_columns(df.columns, "current")
    voltage_col = detect_candidate_columns(df.columns, "voltage")

    assert current_col == "Current (A)"
    assert voltage_col == "Voltage (V)"


def test_prepare_analysis_data_cleans_invalid_rows_and_preserves_order():
    df = pd.DataFrame(
        {
            "current_A": [0.0, 1.0, np.nan, 3.0, 4.0, 5.0],
            "voltage_V": [0.1, 2.0, 3.0, np.inf, 8.2, 10.3],
        }
    )

    prepared = prepare_analysis_data(df, "current_A", "voltage_V")

    assert prepared["original_rows"] == 6
    assert prepared["valid_rows"] == 4
    assert prepared["dropped_rows"] == 2
    # Rows with a missing current or non-finite voltage are both removed as
    # paired observations; retained measurements must remain row-aligned.
    assert np.allclose(prepared["current"], [0.0, 1.0, 4.0, 5.0])
    assert np.allclose(prepared["voltage"], [0.1, 2.0, 8.2, 10.3])
