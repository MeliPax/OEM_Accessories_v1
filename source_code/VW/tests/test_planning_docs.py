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
# item IDs (idea 015): NNN-Kn for a doc, DInn-Sn for a data issue; a decision set is a range "005-D4 – 005-D12"
ITEM = r'(?:\d{3}|DI\d{2})-[A-Z]\d*'
ITEM_REF = re.compile(rf'(?<![\w-])({ITEM})(?![\w-])')
KINDS = set('DTPUAS')
OPEN_ITEM_ROW = re.compile(rf'^\| ({ITEM}(?: – {ITEM})?) \| [^|]+ \| [^|]+ \| [^|]+ \| ([^|]+) \| ([^|]*) \|$', re.M)
OLD_ITEM_REF = re.compile(r'\bOI-\d{2}\b')


def header(text):
    """The **Field:** lines before the first ## heading."""
    head = text.split('\n## ', 1)[0]
    return dict(re.findall(r'^\*\*([A-Za-z ]+):\*\* (.*)$', head, re.M))


def stage(status):
    return status.split(' (')[0].strip()


def expand(item_id):
    """'005-D4 – 005-D12' -> {'005-D4', ..., '005-D12'}; a single ID -> {itself}."""
    first, _, last = item_id.partition(' – ')
    if not last:
        return {first}
    stem = first.rstrip('0123456789')
    return {f'{stem}{n}' for n in range(int(first[len(stem):]), int(last[len(stem):]) + 1)}


def check_items(root, docs, ideas):
    """Idea 015: open_items.md IDs say where they live, and every reference resolves."""
    problems = []
    items_text = (root / 'open_items.md').read_text(encoding='utf-8')
    rows = OPEN_ITEM_ROW.findall(items_text)
    known = set().union(*(expand(i) for i, _, _ in rows)) if rows else set()
    was = {r for _, _, w in rows for r in OLD_ITEM_REF.findall(w)}
    issues = {f'DI{n}' for n in re.findall(r'^### DI-(\d{2})$', (root / 'data_issues.md').read_text(encoding='utf-8'), re.M)}
    texts = {name: p.read_text(encoding='utf-8') for name, p in docs.items()}
    texts['data_issues.md'] = (root / 'data_issues.md').read_text(encoding='utf-8')

    for line in items_text.split('\n'):
        if re.match(r'^\| OI-\d{2} \|', line):
            problems.append(f'open_items.md: {line.split("|")[1].strip()} is an old OI-NN ID; use NNN-Kn (idea 015)')
    for item_id, status, _ in rows:
        prefix, kind = item_id.split('-')[0], item_id.split('-')[1][0]
        if kind not in KINDS:
            problems.append(f'open_items.md: {item_id}: kind "{kind}" is not one of {", ".join(sorted(KINDS))}')
        if prefix not in ideas | issues | {'000'}:
            problems.append(f'open_items.md: {item_id}: no doc or data issue {prefix}')
        if status.strip() == 'Open':
            first = item_id.split(' – ')[0]
            where = [t for n, t in texts.items() if (n.split('/')[-1][:3] == prefix or
                                                      (prefix.startswith('DI') and n == 'data_issues.md'))]
            if not any(first in t for t in where):
                problems.append(f'open_items.md: open item {first} is not named in its doc ({prefix})')

    readme = (root / 'README.md').read_text(encoding='utf-8')
    for name, text in list(texts.items()) + [('README.md', readme)]:
        own = name.split('/')[-1][:3]
        for ref in sorted({r for r in ITEM_REF.findall(text)} - known):
            prefix, kind = ref.split('-')[0], ref.split('-')[1][0]
            if kind == 'D' and prefix == own:          # a decision in its own idea's table or ID note
                continue
            if kind in KINDS and prefix in ideas | issues:
                problems.append(f'{name}: {ref} is mentioned but not in open_items.md')
        for ref in sorted(set(OLD_ITEM_REF.findall(text)) - was):
            problems.append(f'{name}: {ref} is mentioned but no open_items.md row has it as Was')
    nexts = [(n, header(t).get('Next', '')) for n, t in texts.items() if n != 'data_issues.md']
    nexts += [(f'README.md index ({path})', nxt) for _, path, _, nxt, _ in INDEX_ROW.findall(readme)]
    for name, nxt in nexts:
        if OLD_ITEM_REF.search(nxt):
            problems.append(f'{name}: the Next line names an old OI-NN ID; use the doc-numbered ID (idea 015)')
    return problems


def check_planning(root):
    """Every way the planning docs can drift apart, as readable problems (empty when all is well)."""
    problems = []
    docs = {f'{folder}/{p.name}': p for folder in FOLDERS for p in sorted((root / folder).glob('*.md'))}
    index = {path: (number, st.strip(), nxt.strip(), upd.strip())
             for number, path, st, nxt, upd in INDEX_ROW.findall((root / 'README.md').read_text(encoding='utf-8'))}
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

    return problems + check_items(root, docs, ideas)


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
    ('README.md', '| Idea — approved | completed with plan 009 once testing is signed off (009-T) |',
     '| Plan — approved | completed with plan 009 once testing is signed off (009-T) |',
     'index stage "Plan — approved" but the file says "Idea — approved"'),
    # idea 015: doc-numbered item IDs
    (IDEA, 'signed off (009-T)', 'signed off (009-A9)', '009-A9 is mentioned but not in open_items.md'),
    (IDEA, 'signed off (009-T)', 'signed off (OI-01)', 'the Next line names an old OI-NN ID'),
    (IDEA, '## Decisions\n', '## Decisions\n\nSee OI-99.\n', 'OI-99 is mentioned but no open_items.md row has it as Was'),
    ('open_items.md', '| 015-T |', '| OI-22 |', 'OI-22 is an old OI-NN ID'),
    ('open_items.md', '| 015-T |', '| 099-T |', '099-T: no doc or data issue 099'),
    ('open_items.md', '| 003-A1 |', '| 003-X1 |', 'kind "X" is not one of'),
    ('open_items.md', '| 015-T |', '| 007-U1 |', 'open item 007-U1 is not named in its doc (007)'),
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
