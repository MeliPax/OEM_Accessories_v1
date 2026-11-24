import pandas as pd
import pytest

from conftest import SOURCE
from pipeline.ingest_helpers import (clip_years, filter_by_year_window, read_source, snake_case, to_staging,
                                     validate_staging)
from pipeline.logging_helpers import PipelineFatal


@pytest.fixture(scope='module')
def staged():
    return to_staging(read_source(SOURCE), 'datasets/vw_models_data.csv')


def test_snake_case():
    assert [snake_case(c) for c in ['ModelNumber', 'Style_ID', 'engine_type', 'Description']] == \
           ['model_number', 'style_id', 'engine_type', 'description']


def test_read_source_drops_empty_columns_and_keeps_text():
    df = read_source(SOURCE)
    assert list(df.columns) == ['Description', 'Manufacturer', 'ModelNumber', 'ModelYear']
    assert len(df) == 323 and df['ModelYear'].dtype != 'int64'


def test_staging_keeps_values_and_adds_lineage(staged):
    raw = read_source(SOURCE)
    assert staged['description'].tolist() == raw['Description'].tolist()
    assert {'source_row', 'source_file', 'ingested_at'} <= set(staged.columns)
    assert staged['source_row'].iloc[0] == 2


def test_validate_staging_passes_on_real_data(staged):
    assert len(validate_staging(staged, 'Volkswagen')) == 323


def test_duplicate_key_stops_the_run(staged):
    duplicated = pd.concat([staged, staged.head(1)])
    with pytest.raises(PipelineFatal, match='duplicate'):
        validate_staging(duplicated, 'Volkswagen')


def test_missing_required_column_stops_the_run(staged):
    with pytest.raises(PipelineFatal, match='model_number'):
        validate_staging(staged.drop(columns=['model_number']), 'Volkswagen')


def window(min_year, max_year):
    return {'min_model_year': min_year, 'max_model_year': max_year, 'datasets': {
        'vw_models': {'year_rule': 'single_year', 'year_column': 'model_year'},
        'accessories': {'year_rule': 'range_overlap', 'start_column': 'min_year', 'end_column': 'max_year'}}}


def test_single_year_window_on_real_data(staged):
    assert len(filter_by_year_window(staged, window(2020, None), 'vw_models')) == 269
    assert len(filter_by_year_window(staged, window(2020, 2024), 'vw_models')) == 197
    assert len(filter_by_year_window(staged, window(2019, None), 'vw_models')) == 323


def test_range_overlap_window_for_accessories():
    acc = pd.DataFrame({'part': ['a', 'b', 'c', 'd'],
                        'min_year': ['2018', '2015', '2022', '2025'],
                        'max_year': ['2022', '2019', '2024', '2026']})
    open_ended = filter_by_year_window(acc, window(2020, None), 'accessories')['part'].tolist()
    capped = filter_by_year_window(acc, window(2020, 2023), 'accessories')['part'].tolist()
    assert open_ended == ['a', 'c', 'd']
    assert capped == ['a', 'c']


def test_clip_years_to_window():
    assert clip_years(2018, 2022, window(2020, None)) == [2020, 2021, 2022]
    assert clip_years(2018, 2026, window(2020, 2024)) == [2020, 2021, 2022, 2023, 2024]
