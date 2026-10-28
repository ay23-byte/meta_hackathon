"""Regression tests for uploaded measurements, selections and chart contents."""
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pytest
from streamlit.testing.v1 import AppTest

from data_io import read_csv_robust
from fitting_core import fit_linear
from visualization_core import build_chart

ROOT = Path(__file__).resolve().parents[1]


def test_uploaded_time_signal_and_current_voltage_use_real_rows():
    for raw, x, y, expected in [
        (b'time_s,signal_mV\n10,5\n20,9\n30,12\n', 'time_s', 'signal_mV', [(10, 5), (20, 9), (30, 12)]),
        (b'current_A,voltage_V\n0.2,3\n0.4,7\n0.6,11\n', 'current_A', 'voltage_V', [(0.2, 3), (0.4, 7), (0.6, 11)]),
    ]:
        loaded = read_csv_robust(io.BytesIO(raw), source_name='upload.csv')
        before = loaded.frame.copy(deep=True)
        chart = build_chart('scatter', loaded.frame, {'x': x, 'y': y, 'unit_x': 's', 'unit_y': 'mV', 'show_fit': False})
        assert chart.valid and list(chart.frame[['x', 'y']].itertuples(index=False, name=None)) == expected
        assert chart.columns == [x, y]
        spec = chart.chart.to_dict()
        assert spec['encoding']['x']['title'] == f'{x} (s)'
        assert spec['encoding']['y']['title'] == f'{y} (mV)'
        pd.testing.assert_frame_equal(before, loaded.frame)


def test_scatter_does_not_exclude_rows_for_unused_uncertainty():
    frame = pd.DataFrame({'x': [0, 1, 2, 3, np.inf, 5], 'y': [10, 20, 30, None, 50, 'bad'],
                          'sigma': [1, np.nan, 1, 1, 1, 1], 'group': ['a', 'b', 'a', 'a', 'b', 'a']})
    spec = build_chart('scatter', frame, {'x': 'x', 'y': 'y', 'uncertainty': 'sigma', 'group': 'group', 'show_fit': False})
    assert spec.frame[['x', 'y']].values.tolist() == [[0, 10], [1, 20], [2, 30]]
    assert '3 valid row(s); 3 row(s) excluded' in spec.notes[0]
    assert spec.frame['group'].tolist() == ['a', 'b', 'a']
    error = build_chart('errorbar', frame, {'x': 'x', 'y': 'y', 'uncertainty': 'sigma'})
    assert len(error.frame) == 2


def test_time_series_is_grouped_line_and_fit_is_opt_in():
    frame = pd.DataFrame({'t': [2, 1, 3, 4], 'y': [4, 2, 6, 8], 'g': ['a', 'a', 'b', 'b']})
    config = {'x': 't', 'y': 'y', 'group': 'g', 'fit_result': fit_linear(frame.t, frame.y)}
    time_chart = build_chart('time_series', frame, config).chart.to_dict()
    assert time_chart['mark']['type'] == 'line' and time_chart['encoding']['detail']['field'] == 'group'
    assert build_chart('scatter', frame, dict(config, show_fit=False)).chart.to_dict()['mark']['type'] == 'circle'
    fitted = build_chart('scatter', frame, dict(config, show_fit=True))
    assert len(fitted.chart.to_dict()['layer']) == 2
    assert any('not measured data' in note for note in fitted.notes)


def chart_data(at):
    proto = at.get('vega_lite_chart')[0].proto
    spec = json.loads(proto.spec)
    data = pa.ipc.open_stream(io.BytesIO(proto.datasets[0].data.data)).read_all().to_pandas()
    return spec, data


def select(at, name):
    return next(item for item in at.selectbox if item.label == name)


def test_upload_replacement_and_axis_changes_refresh_actual_vega_data(monkeypatch):
    monkeypatch.delenv('BASETEN_API_KEY', raising=False)
    at = AppTest.from_file(str(ROOT / 'general_app.py'), default_timeout=180).run()
    first = b'time,signal,other,group\n10,100,900,a\n11,110,800,b\n12,120,700,a\n13,130,600,b\n'
    at.file_uploader[0].set_value(('same.csv', first, 'text/csv')).run()
    assert not at.exception and not at.error
    x, y = select(at, 'X column (independent)'), select(at, 'Y column (dependent)')
    assert x.value == 'time' and y.value == 'signal'
    assert 'group' not in x.options and 'group' not in y.options
    spec, plotted = chart_data(at)
    assert plotted['x'].tolist() == [10, 11, 12, 13]
    assert plotted['y'].tolist() == [100, 110, 120, 130]
    assert spec['mark']['type'] == 'circle'
    select(at, 'Y column (dependent)').set_value('other').run()
    assert chart_data(at)[1]['y'].tolist() == [900, 800, 700, 600]
    select(at, 'X column (independent)').set_value('signal').run()
    assert chart_data(at)[1]['x'].tolist() == [100, 110, 120, 130]
    second = b'time,signal,other,group\n20,9000,5,a\n21,9100,6,b\n22,9200,7,a\n23,9300,8,b\n'
    at.file_uploader[0].set_value(('same.csv', second, 'text/csv')).run()
    assert not at.exception and not at.error
    x_name, y_name = select(at, 'X column (independent)').value, select(at, 'Y column (dependent)').value
    expected = pd.read_csv(io.BytesIO(second))
    plotted = chart_data(at)[1]
    assert plotted['x'].tolist() == expected[x_name].tolist()
    assert plotted['y'].tolist() == expected[y_name].tolist()
    assert 10 not in plotted['x'].tolist() and 130 not in plotted['y'].tolist()


def test_empty_unsuitable_and_duplicate_headers_have_clear_feedback(monkeypatch):
    monkeypatch.delenv('BASETEN_API_KEY', raising=False)
    at = AppTest.from_file(str(ROOT / 'general_app.py'), default_timeout=180).run()
    at.file_uploader[0].set_value(('empty.csv', b'', 'text/csv')).run()
    assert not at.exception and any('empty' in e.value.lower() for e in at.error)
    at.file_uploader[0].set_value(('text.csv', b'name,kind\na,red\nb,blue\nc,green\n', 'text/csv')).run()
    assert not at.exception and any('at least two columns' in i.value for i in at.info)
    at.file_uploader[0].set_value(('duplicate.csv', b'x,x\n1,3\n2,5\n3,7\n4,9\n', 'text/csv')).run()
    assert not at.exception and not at.error
    assert any('Duplicate column' in w.value for w in at.warning)
    assert chart_data(at)[1]['y'].tolist() == pytest.approx([3, 5, 7, 9])


def test_user_can_toggle_model_overlay_and_axis_units(monkeypatch):
    monkeypatch.delenv('BASETEN_API_KEY', raising=False)
    at = AppTest.from_file(str(ROOT / 'general_app.py'), default_timeout=180).run()
    at.file_uploader[0].set_value(('measure.csv', b'time,signal\n1,4\n2,7\n3,10\n4,13\n', 'text/csv')).run()
    next(w for w in at.text_input if w.label == 'X unit (optional)').set_value('s')
    next(w for w in at.text_input if w.label == 'Y unit (optional)').set_value('mV')
    at.run()
    spec, _ = chart_data(at)
    assert spec['encoding']['x']['title'] == 'time (s)'
    assert spec['encoding']['y']['title'] == 'signal (mV)'
    next(w for w in at.checkbox if w.label == 'Overlay selected fitted model on scatter').check().run()
    assert not at.exception and len(chart_data(at)[0]['layer']) == 2
    assert any('not measured data' in c.value for c in at.caption)


def test_duplicate_headers_after_trimming_are_rejected_safely():
    from data_io import DataImportError

    with pytest.raises(DataImportError, match='duplicates after whitespace normalization'):
        read_csv_robust(b'x, x \n1,2\n3,4\n', source_name='trim.csv')


def test_uploaded_sample_filename_does_not_imply_physical_axes(monkeypatch):
    monkeypatch.delenv('BASETEN_API_KEY', raising=False)
    at = AppTest.from_file(str(ROOT / 'general_app.py'), default_timeout=180).run()
    at.file_uploader[0].set_value(('sample_voltage_current.csv', b'time,signal\n1,2\n2,4\n3,6\n4,8\n', 'text/csv')).run()
    assert not at.exception and not at.error
    assert 'Slope (ΔV / ΔI)' not in [metric.label for metric in at.metric]
    assert chart_data(at)[1]['x'].tolist() == [1, 2, 3, 4]
