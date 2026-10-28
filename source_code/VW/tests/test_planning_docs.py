"""The planning docs stay in step (plan 010): headers, status words, the index, open items and checkpoints.

The index in planning/README.md can then be trusted without opening the docs it lists.
"""

import re
import shutil

import pytest

from conftest import VW_DIR, replace_in

PLANNING = VW_DIR / 'planning'
FOLDERS = ('ideas', 'plans', 'completed')
FIELDS = ('Status', 'Updated', 'Next', 'Links', 'Summary')
STATUSES = {
    'ideas': {'Seed', 'Idea — waiting for decisions', 'Idea — approved', 'Completed', 'Dropped'},
    'plans': {'Plan — waiting for approval', 'Plan — approved', 'Building', 'Built — in user testing', 'Dropped'},
    'completed': {'Completed'},
}
INDEX_ROW = re.compile(r'^\| (\d{3}) \| \[[^\]]+\]\(([^)]+)\) \| ([^|]+) \| ([^|]*) \| ([^|]+) \|$', re.M)
OPEN_ITEM_ROW = re.compile(r'^\| (OI-\d{2}) \|', re.M)
OPEN_ITEM_REF = re.compile(r'\bOI-\d{2}\b')


def header(text):
    """The **Field:** lines before the first ## heading."""
    head = text.split('\n## ', 1)[0]
    return dict(re.findall(r'^\*\*([A-Za-z ]+):\*\* (.*)$', head, re.M))


def stage(status):
    return status.split(' (')[0].strip()


def check_planning(root):
    """Every way the planning docs can drift apart, as readable problems (empty when all is well)."""
    problems = []
    docs = {f'{folder}/{p.name}': p for folder in FOLDERS for p in sorted((root / folder).glob('*.md'))}
    index = {path: (number, st.strip(), nxt.strip(), upd.strip())
             for number, path, st, nxt, upd in INDEX_ROW.findall((root / 'README.md').read_text(encoding='utf-8'))}
    open_items = set(OPEN_ITEM_ROW.findall((root / 'open_items.md').read_text(encoding='utf-8')))
    ideas = {p.name[:3] for p in (root / 'ideas').glob('*.md')}

    for name, path in docs.items():
        text = path.read_text(encoding='utf-8')
        fields = header(text)
        folder = name.split('/')[0]
        for missing in [f for f in FIELDS if not fields.get(f)]:
            problems.append(f'{name}: header field "{missing}" is missing')
        status = stage(fields.get('Status', ''))
        if fields.get('Status') and status not in STATUSES[folder]:
            problems.append(f'{name}: status "{status}" is not one of {", ".join(sorted(STATUSES[folder]))}')
        if status == 'Building' and not fields.get('Checkpoint'):
            problems.append(f'{name}: a Building plan needs a **Checkpoint:** line')
        if folder != 'ideas' and name.split('/')[1][:3] not in ideas:
            problems.append(f'{name}: no idea with number {name.split("/")[1][:3]}')
        if folder == 'completed' and '\n## Completion notes' not in text:
            problems.append(f'{name}: a completed plan needs a "## Completion notes" section')
        if name not in index:
            problems.append(f'{name}: not in the README index')
        else:
            number, st, nxt, upd = index[name]
            if number != path.name[:3]:
                problems.append(f'{name}: index number {number} does not match the file')
            if st != status:
                problems.append(f'{name}: index stage "{st}" but the file says "{status}"')
            if nxt != fields.get('Next', ''):
                problems.append(f'{name}: index Next differs from the file\'s **Next:** line')
            if upd != fields.get('Updated', ''):
                problems.append(f'{name}: index Updated {upd} but the file says {fields.get("Updated")}')

    for name in sorted(set(index) - set(docs)):
        problems.append(f'README index lists {name}, which does not exist')

    texts = [p.read_text(encoding='utf-8') for p in docs.values()] + [(root / 'README.md').read_text(encoding='utf-8')]
    for ref in sorted({r for t in texts for r in OPEN_ITEM_REF.findall(t)} - open_items):
        problems.append(f'{ref} is mentioned but not in open_items.md')
    return problems


def test_the_planning_docs_are_in_step():
    assert check_planning(PLANNING) == []


@pytest.fixture
def planning_copy(tmp_path):
    target = tmp_path / 'planning'
    shutil.copytree(PLANNING, target)
    return target


IDEA = 'ideas/009_human_verified_vehicle_facts_design.md'
PLAN = 'plans/010_work_process_and_tracking.md'


@pytest.mark.parametrize('file, old, new, problem', [
    (IDEA, '**Summary:** ', '**Summery:** ', 'header field "Summary" is missing'),
    (IDEA, '**Status:** Idea — approved', '**Status:** Idea — done', 'status "Idea — done" is not one of'),
    (PLAN, '**Status:** Built — in user testing', '**Status:** Building', 'a Building plan needs a **Checkpoint:** line'),
    (IDEA, '**Updated:** 2026-10-28', '**Updated:** 2026-10-29', 'index Updated 2026-10-28 but the file says 2026-10-29'),
    (IDEA, '**Next:** build plan 009', '**Next:** build plan 009 (OI-99)', 'OI-99 is mentioned but not in open_items.md'),
    ('README.md', '| Idea — approved | build plan 009 |', '| Plan — approved | build plan 009 |',
     'index stage "Plan — approved" but the file says "Idea — approved"'),
])
def test_drift_is_caught(planning_copy, file, old, new, problem):
    replace_in(planning_copy / file, old, new)
    assert any(problem in p for p in check_planning(planning_copy)), check_planning(planning_copy)


def test_unindexed_plan_without_idea_and_completed_without_notes(planning_copy):
    (planning_copy / 'plans' / '099_orphan.md').write_text(
        '# 099 — Orphan: Plan\n\n**Status:** Plan — approved\n**Updated:** 2026-10-28\n**Next:** x\n'
        '**Links:** x\n**Summary:** x\n\n## Outcome\n', encoding='utf-8')
    (planning_copy / 'completed').mkdir(exist_ok=True)
    shutil.copy(planning_copy / 'plans' / '007_comment_text_cleaning.md',
                planning_copy / 'completed' / '007_comment_text_cleaning.md')
    replace_in(planning_copy / 'completed' / '007_comment_text_cleaning.md',
               '**Status:** Built — in user testing', '**Status:** Completed')
    problems = check_planning(planning_copy)
    assert 'plans/099_orphan.md: not in the README index' in problems
    assert 'plans/099_orphan.md: no idea with number 099' in problems
    assert 'completed/007_comment_text_cleaning.md: a completed plan needs a "## Completion notes" section' in problems


def test_index_row_for_a_missing_file(planning_copy):
    (planning_copy / 'ideas' / '011_requirements_and_documentation_design.md').unlink()
    assert ('README index lists ideas/011_requirements_and_documentation_design.md, which does not exist'
            in check_planning(planning_copy))
