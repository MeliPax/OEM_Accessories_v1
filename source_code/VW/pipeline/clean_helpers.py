"""Text cleaning, moved from oem_access_data_analysis.ipynb (same behaviour).

Cleaning order: aliases -> trim / collapse spaces -> remove repeated words.
e.g. "Jetta GLI GLI" -> "Jetta GLI", "ID. Buzz ID. Buzz 1st Edition" -> "ID. Buzz 1st Edition"
"""

import re

from pipeline.logging_helpers import log_change


def apply_aliases(value, aliases):
    """Replace each alias phrase with its standard name (case-insensitive, whole words only)."""
    if not isinstance(value, str) or not aliases:
        return value
    for alias, standard in aliases.items():
        value = re.sub(rf'\b{re.escape(alias)}\b', standard, value, flags=re.IGNORECASE)
    return value


def remove_repeated_words(value):
    """Drop repeated words, comparing case-insensitively and keeping the first occurrence as written."""
    if not isinstance(value, str):
        return value
    seen = set()
    words = []
    for word in value.strip().split():
        if word.lower() not in seen:
            seen.add(word.lower())
            words.append(word)
    return ' '.join(words)


def clean_value(value, aliases=None):
    """Clean one value and explain what changed: returns (cleaned, [(rule, before, after, detail), ...])."""
    steps = []
    if not isinstance(value, str):
        return value, steps

    aliased = apply_aliases(value, aliases)
    if aliased != value:
        used = [f'{a} -> {s}' for a, s in (aliases or {}).items()
                if re.search(rf'\b{re.escape(a)}\b', value, flags=re.IGNORECASE)]
        steps.append(('alias', value, aliased, '; '.join(used)))

    spaced = ' '.join(aliased.split())
    if spaced != aliased:
        steps.append(('trim_spaces', aliased, spaced, 'extra spaces removed'))

    deduped = remove_repeated_words(spaced)
    if deduped != spaced:
        kept = {w.lower() for w in deduped.split()}
        removed, seen = [], set()
        for word in spaced.split():
            if word.lower() in seen and word.lower() in kept:
                removed.append(word)
            seen.add(word.lower())
        steps.append(('remove_repeated_words', spaced, deduped, 'removed: ' + ', '.join(removed)))
    return deduped, steps


def clean_text_column(df, column, new_column=None, aliases=None):
    """Clean a text column into a new column (<column>_clean by default). Notebook-compatible."""
    df = df.copy()
    new_column = new_column or f'{column}_clean'
    df[new_column] = df[column].map(lambda v: clean_value(v, aliases)[0])
    changed = (df[column].astype(str) != df[new_column].astype(str)).sum()
    print(f'Cleaned {column} -> {new_column}: {changed} of {len(df)} values changed')
    return df


def clean_descriptions(df, aliases, ctx=None, step='clean'):
    """Pipeline step: add description_clean, logging each change with the rule that made it."""
    df = df.copy()
    cleaned = []
    for _, row in df.iterrows():
        value, steps = clean_value(row['description'], aliases)
        for rule, before, after, detail in steps:
            log_change(ctx, step, row, 'description_clean', before, after, rule, detail)
        cleaned.append(value)
    df['description_clean'] = cleaned
    return df
