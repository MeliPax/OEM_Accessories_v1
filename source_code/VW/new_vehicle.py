"""Set up a new vehicle file from the template: config/vehicles/_template.yaml -> config/vehicles/<model>.yaml.

    python new_vehicle.py "ID.4"           # from source_code/VW -> config/vehicles/id4.yaml
    python new_vehicle.py "Atlas"

Fills make and model, lists the model's submodels, and never overwrites a file. The model must already be
in config/models.yaml. Exit code: 0 = file created, 1 = nothing created (the reason is printed).
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

VW_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(VW_DIR))

from pipeline import config_helpers as cfg                                    # noqa: E402

TEMPLATE = '_template.yaml'
START, RULES = '# ---------------------------------------------------------------- start here', \
               '# ---------------------------------------------------------------- the rules'


def file_name(model):
    """ID.4 -> id4.yaml, ID. Buzz -> id_buzz.yaml, e-Golf -> e_golf.yaml."""
    return re.sub(r'[\s-]+', '_', model.replace('.', '').strip().lower()).strip('_') + '.yaml'


def create_vehicle_file(model, config_dir=VW_DIR / 'config', today=None):
    """Write config/vehicles/<model>.yaml from the template. Returns the path; raises ValueError (nothing
    written) if the model isn't in models.yaml or already has a file."""
    config_dir = Path(config_dir)
    models = cfg.read_yaml(config_dir / 'models.yaml')
    names = {name.lower(): name for name in models['models']}
    if model.strip().lower() not in names:
        raise ValueError(f'"{model}" is not in config/models.yaml (known: {", ".join(models["models"])}). '
                         f'Add it there first.')
    model = names[model.strip().lower()]
    for path in cfg.vehicle_files(config_dir):
        if (cfg.read_yaml(path) or {}).get('model') == model:
            raise ValueError(f'{model} already has config/vehicles/{path.name}; edit that file.')
    path = config_dir / 'vehicles' / file_name(model)
    if path.exists():
        raise ValueError(f'config/vehicles/{path.name} already exists; nothing was overwritten.')

    text = (config_dir / 'vehicles' / TEMPLATE).read_text(encoding='utf-8')
    submodels = ', '.join((models['models'][model] or {}).get('submodels') or {}) or 'none (base model only)'
    head, _, rest = text.partition(START)
    _, _, rest = rest.partition(RULES)
    head = (f'# Option sets for the {models["make"]} {model}: what each year range can have.\n'
            f'# Created {(today or date.today()).isoformat()} from {TEMPLATE}. Uncomment and edit the examples '
            f'you need, delete the rest.\n#\n')
    text = head + RULES + rest
    text = re.sub(r'^make:.*$', f'make: {models["make"]}', text, count=1, flags=re.M)
    text = re.sub(r'^model:.*$', f'model: {model}\n# submodels in models.yaml: {submodels}', text, count=1,
                  flags=re.M)
    path.write_text(text, encoding='utf-8')
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description='Set up config/vehicles/<model>.yaml from the template.')
    parser.add_argument('model', help='model name as in config/models.yaml, e.g. "ID.4"')
    args = parser.parse_args(argv)
    try:
        path = create_vehicle_file(args.model)
    except ValueError as e:
        print(f'not created: {e}')
        return 1
    print(f'created: config/vehicles/{path.name}\n'
          f'next: 1) add the option sets per year range (examples in the file)\n'
          f'      2) python run_ingest.py -> fix any CONFG_ / VEH_VALID_NOT_IN_CONFIG flags\n'
          f'      3) once a person has checked it: status: reviewed, reviewed_by, reviewed_on')
    return 0


if __name__ == '__main__':
    sys.exit(main())
