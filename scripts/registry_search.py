#!/usr/bin/env python3
"""Shortlist databases, tools, skills and know-how for a task (stdlib only, read-only).

Stage one of two-stage retrieval: score registry entries by keyword overlap with the
query and return a capped shortlist. The AI then reads only the chosen know-how and
skill documents. A shortlist is a suggestion; availability must be confirmed in the
current environment before use.
"""
import argparse
import json
from pathlib import Path
import re
import sys

from project_io import encoded, load, local

SKILL_ROOT = Path(__file__).resolve().parents[1]
SEED = SKILL_ROOT / 'assets' / 'capabilities' / 'registry.json'
KINDS = {'database', 'tool', 'skill', 'know_how'}
STATUSES = {'candidate', 'verified', 'deprecated'}
REQUIRED = ('id', 'kind', 'summary', 'tags', 'access', 'license', 'status')


def tokens(text):
    """Latin words plus CJK character bigrams, so Chinese queries match without a segmenter."""
    text = str(text).lower()
    words = set(re.findall(r'[a-z0-9][a-z0-9\-\.+]*', text))
    for run in re.findall(r'[一-鿿]+', text):
        words.update(run[i:i + 2] for i in range(len(run) - 1))
        if len(run) == 1:
            words.add(run)
    return words


def validate(entries, source):
    problems = []
    seen = set()
    for row in entries:
        identity = row.get('id', '?') if isinstance(row, dict) else '?'
        if not isinstance(row, dict):
            problems.append(f'{source}: entry is not an object')
            continue
        for key in REQUIRED:
            if key not in row:
                problems.append(f'{source}:{identity}: missing {key}')
        if row.get('kind') not in KINDS:
            problems.append(f'{source}:{identity}: invalid kind')
        if row.get('status') not in STATUSES:
            problems.append(f'{source}:{identity}: invalid status')
        if row.get('status') == 'verified' and not (row.get('verified_at') and row.get('evidence')):
            problems.append(f'{source}:{identity}: verified entries need verified_at and evidence')
        if source == 'skill registry' and row.get('doc') and not (SEED.parent / row['doc']).is_file():
            problems.append(f'{source}:{identity}: know-how doc not found: {row["doc"]}')
        if not isinstance(row.get('tags', []), list):
            problems.append(f'{source}:{identity}: tags must be a list')
        if identity in seen:
            problems.append(f'{source}:{identity}: duplicate id')
        seen.add(identity)
    return problems


def registry(project=None):
    seed = json.loads(SEED.read_text(encoding='utf-8'))
    entries = {row['id']: dict(row, origin='skill') for row in seed.get('entries', [])}
    problems = validate(seed.get('entries', []), 'skill registry')
    if project:
        path = local(Path(project).resolve(), '_pm/capabilities.json')
        if path.is_file():
            extra = load(path).get('entries', [])
            problems += validate(extra, '_pm/capabilities.json')
            for row in extra:
                if isinstance(row, dict) and row.get('id'):
                    entries[row['id']] = dict(row, origin='project')  # project entries override seed
    return entries, problems


def search(entries, query, kinds=None, limit=8, include_deprecated=False):
    wanted = tokens(query)
    scored = []
    for row in entries.values():
        if kinds and row.get('kind') not in kinds:
            continue
        if row.get('status') == 'deprecated' and not include_deprecated:
            continue
        tag_tokens = set().union(*(tokens(t) for t in row.get('tags', []))) if row.get('tags') else set()
        summary_tokens = tokens(row.get('summary', '')) | tokens(row.get('id', ''))
        score = 2 * len(wanted & tag_tokens) + len(wanted & summary_tokens)
        if score:
            score += 1 if row.get('status') == 'verified' else 0
            score += 1 if row.get('origin') == 'project' else 0
            scored.append((score, row))
    scored.sort(key=lambda item: (-item[0], item[1]['id']))
    keys = ('id', 'kind', 'summary', 'status', 'license', 'pitfalls', 'doc', 'origin')
    return [dict({k: row.get(k) for k in keys if row.get(k) is not None}, score=score)
            for score, row in scored[:limit]]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--project', help='Project whose _pm/capabilities.json extends the seed registry')
    parser.add_argument('--query', help='Task keywords, Chinese or English')
    parser.add_argument('--kind', action='append', choices=sorted(KINDS))
    parser.add_argument('--limit', type=int, default=8)
    parser.add_argument('--include-deprecated', action='store_true')
    parser.add_argument('--lint', action='store_true', help='Validate registry entries only')
    args = parser.parse_args(argv)
    try:
        entries, problems = registry(args.project)
        if args.lint or not args.query:
            print(encoded({'ok': not problems, 'entries': len(entries), 'problems': problems}))
            return 0 if not problems else 1
        hits = search(entries, args.query, set(args.kind or []), max(1, args.limit), args.include_deprecated)
        result = {'ok': True, 'query': args.query, 'shortlist': hits, 'problems': problems,
                  'scope': '候选短名单；使用前确认当前环境可用，并读取对应 know-how 或技能说明。'}
        if not hits:
            result['hint'] = ('没有命中：换成任务动词或数据类型（如“药物敏感性”“单细胞”“生存”），'
                              '或把这个任务需要的资源登记到 _pm/capabilities.json（先标 candidate）。'
                              '未命中不代表没有合适资源。')
        print(encoded(result))
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(encoded({'ok': False, 'error': str(error)}))
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
