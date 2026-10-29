import re
from datetime import date

import pytest

import new_vehicle
from conftest import CONFIG_DIR
from pipeline import config_helpers as cfg

TEMPLATE = CONFIG_DIR / 'vehicles' / '_template.yaml'


def uncomment_examples(path):
    """Turn every commented example line ('  # - years: ...', '  #   trim: ...') into YAML."""
    text = path.read_text(encoding='utf-8')
    path.write_text(re.sub(r'^  # (  |- )', r'  \1', text, flags=re.M), encoding='utf-8')


def load(config_dir):
    taxonomy = cfg.validate_taxonomy(cfg.load_taxonomy(config_dir))
    sets = cfg.load_option_sets(config_dir, taxonomy)
    return taxonomy, sets, cfg.load_verified(config_dir, taxonomy, sets)


def test_the_template_is_never_read_by_the_pipeline(option_sets):
    assert TEMPLATE.exists()
    assert TEMPLATE not in cfg.vehicle_files(CONFIG_DIR)
    assert not [s for s in option_sets if s['file'].startswith('_')]


def test_the_template_lists_every_keyword_value(taxonomy):
    text = TEMPLATE.read_text(encoding='utf-8')
    for category, values in cfg.keyword_values(taxonomy).items():
        if category == 'inventory_status':
            continue                                   # metadata, never an option
        line = re.search(rf'^#   {category} .*(?:\n#      .*)*', text, flags=re.M)
        assert line, f'{category} is missing from the template value list'
        for value in values:
            assert value in line.group(0), f'{category} value "{value}" is missing from the template'


@pytest.mark.parametrize('model, name', [('ID.4', 'id4.yaml'), ('ID. Buzz', 'id_buzz.yaml'),
                                         ('e-Golf', 'e_golf.yaml'), ('Atlas', 'atlas.yaml')])
def test_file_name_matches_the_existing_files(model, name):
    assert new_vehicle.file_name(model) == name


def test_a_new_file_loads_and_every_example_is_valid(config_copy):
    (config_copy / 'vehicles' / 'golf.yaml').unlink()
    path = new_vehicle.create_vehicle_file('golf', config_copy, today=date(2026, 10, 29))
    assert path.name == 'golf.yaml'
    text = path.read_text(encoding='utf-8')
    assert 'model: Golf\n# submodels in models.yaml: GTI, R, Alltrack, SportWagen' in text
    assert 'Created 2026-10-29 from _template.yaml' in text and 'start here' not in text
    _, sets, facts = load(config_copy)                 # as created: loads, declares nothing yet
    assert not [s for s in sets if s['model'] == 'Golf'] and not [f for f in facts if f['model'] == 'Golf']

    uncomment_examples(path)
    _, sets, facts = load(config_copy)                 # every example, uncommented: still valid
    golf = [s for s in sets if s['model'] == 'Golf']
    assert len(golf) == 4 and {f['kind'] for f in facts if f['model'] == 'Golf'} == {'never_offered',
                                                                                     'no_parts_expected'}


def test_it_never_overwrites_and_needs_a_known_model(config_copy):
    with pytest.raises(ValueError, match='already has config/vehicles/id4.yaml'):
        new_vehicle.create_vehicle_file('ID.4', config_copy)
    with pytest.raises(ValueError, match='not in config/models.yaml'):
        new_vehicle.create_vehicle_file('Polo', config_copy)
    (config_copy / 'vehicles' / 'beetle.yaml').write_text('# someone else\n', encoding='utf-8')
    with pytest.raises(ValueError, match='nothing was overwritten'):
        new_vehicle.create_vehicle_file('Beetle', config_copy)
    assert (config_copy / 'vehicles' / 'beetle.yaml').read_text(encoding='utf-8') == '# someone else\n'
