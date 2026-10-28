"""Comment text cleaning (planning/ideas/007_comment_text_cleaning_design.md). Pure functions; the rules
come from the text_cleaning block in config/accessories.yaml.

    raw text
      1. decode HTML entities              &amp; -> &
      2. normalize spaces                  non-breaking space, tab, line break -> space
      3. links                             link_rules replace the URL; allowed hosts are kept; others reported
      4. separators -> split               | || and separator tags (<p> </p> <br/>) -> sentences
      5. other tags                        removed, text kept (unknown ones reported)
      6. each sentence                     trimmed, spaces collapsed, "process ." -> "process.",
                                           sentence_end added when it has no ending punctuation (not after a link)
      7. join                              with join_with
"""

import html
import re
from urllib.parse import urlparse

URL = re.compile(r'(?:https?://|www\.)[^\s<>"\']+', re.IGNORECASE)        # a link stops at a tag or a space
URL_TRAILING = '.,;:!?)'
TAG = re.compile(r'<\s*/?\s*([A-Za-z][A-Za-z0-9]*)\b[^>]*>')
SPACES = re.compile(r'[   \t\r\n]')
SPACE_BEFORE_PUNCTUATION = re.compile(r'\s+([.,;:!?])(?=\s|$)')            # only when the mark ends the word
SPLIT = '\x01'
KEPT_LINK = '\x00{}\x00'                                                    # placeholder while the text is cut up
KEPT_LINK_AT_END = re.compile(r'\x00\d+\x00$')


def find_links(text):
    """[(start, end, url)] for every link, without trailing punctuation (a full stop after a URL is text)."""
    links = []
    for m in URL.finditer(text):
        url = m.group(0).rstrip(URL_TRAILING)
        if url:
            links.append((m.start(), m.start() + len(url), url))
    return links


def link_host(url):
    return urlparse(url if '://' in url else f'http://{url}').netloc.lower()


def link_rule_for(url, rules):
    return next((r for r in rules if (url == r['match'] if r['match_type'] == 'exact'
                                      else url.startswith(r['match']))), None)


def clean_text(text, rules):
    """Clean one text. Returns {text, rules (names of the rules that changed it, in order), links
    [(url, action, detail)] with action replaced | allowed | unreviewed, unknown_tags {name}}."""
    fired, links, unknown = [], [], set()

    def note(rule):
        if rule not in fired:
            fired.append(rule)

    out = str(text)
    if rules['decode_html_entities']:
        decoded = html.unescape(out)
        if decoded != out:
            note('html_entities')
        out = decoded
    spaced = SPACES.sub(' ', out)
    if spaced != out:
        note('spaces')
    out = spaced

    kept = []
    for start, end, url in reversed(find_links(out)):
        rule = link_rule_for(url, rules['link_rules'])
        if rule:
            links.append((url, 'replaced', rule['replace_with']))
            note(f'link_rule: {url} -> {rule["replace_with"]}')
            out = out[:start] + rule['replace_with'] + out[end:]
            continue
        links.append((url, 'allowed' if link_host(url) in rules['allowed_link_hosts'] else 'unreviewed', ''))
        kept.append(url)
        out = out[:start] + KEPT_LINK.format(len(kept) - 1) + out[end:]
    links.reverse()

    def tag(m):
        name = m.group(1).lower()
        note('html_tags')
        if name in rules['separator_tags']:
            return SPLIT
        if name not in rules['remove_tags']:
            unknown.add(name)
        return ''

    out = TAG.sub(tag, out)
    if rules['pipes'] and '|' in out:
        note('pipes')
        out = out.replace('|', SPLIT)

    sentences = []
    for piece in out.split(SPLIT):
        sentence = ' '.join(piece.split())
        if sentence != piece.strip():
            note('spaces')
        tidy = SPACE_BEFORE_PUNCTUATION.sub(r'\1', sentence)
        if tidy != sentence:
            note('space_before_punctuation')
        if not tidy:
            continue
        if not KEPT_LINK_AT_END.search(tidy) and tidy[-1] not in rules['ending_punctuation']:
            tidy += rules['sentence_end']
            note('sentence_end')
        sentences.append(tidy)
    joined = rules['join_with'].join(sentences)
    for n, url in enumerate(kept):
        joined = joined.replace(KEPT_LINK.format(n), url)
    return {'text': joined, 'rules': fired if joined != text else [], 'links': links, 'unknown_tags': unknown}
