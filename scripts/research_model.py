"""Optional v4 research-model checks: question tree, hypotheses, purpose links, claim basis.

All collections are optional so schema-2 projects without them stay valid. The checks
verify registered links only; whether a question is worth asking is a human judgement.
"""
from pathlib import Path
import re

from project_io import digest, load, local

Q_STATUSES = {'open', 'answered', 'parked', 'dropped', 'superseded'}
H_STATUSES = {'candidate', 'prioritized', 'testing', 'supported', 'refuted', 'inconclusive', 'parked', 'superseded'}
CLAIM_BASES = {'data', 'literature', 'synthesis'}
TYPES = {'secondary', 'omics', 'wet_lab', 'animal', 'clinical_observational', 'diagnostic_prognostic',
         'clinical_trial', 'evidence_synthesis', 'methods'}


def upstream(identity, artifacts):
    """Artifact plus all registered ancestors via depends_on."""
    seen, stack = set(), [identity]
    while stack:
        current = stack.pop()
        if current in seen or current not in artifacts:
            continue
        seen.add(current)
        stack.extend(d.get('id') for d in artifacts[current].get('depends_on', []) if isinstance(d, dict))
    return seen


def independence(audit, identity, row, artifacts):
    """Discovery inputs and validation inputs must not share registered provenance."""
    derived, validated = row.get('derived_from', []), row.get('validated_on', [])
    for key, values in (('derived_from', derived), ('validated_on', validated)):
        if not isinstance(values, list):
            audit.error(f'{identity}.{key}: expected a list of artifact ids')
            return
        for value in values:
            if value not in artifacts:
                audit.error(f'{identity}.{key}: unknown artifact {value}')
    if not derived or not validated:
        return
    direct = set(derived) & set(validated)
    if direct:
        audit.error(f'{identity}: validation reuses discovery inputs {sorted(direct)}; it is not independent')
        return
    discovery = set().union(*(upstream(d, artifacts) for d in derived))
    validation = set().union(*(upstream(v, artifacts) for v in validated))
    shared = discovery & validation
    if shared and not audit.nonempty(row.get('independence')):
        audit.error(f'{identity}: discovery and validation share upstream {sorted(shared)}; '
                    'justify in independence or use independent data')


def run_starts(audit, state):
    """Map task id -> [(run id, started_at)] from actual run records that name a task."""
    result = {}
    for row in state.get('runs', []):
        if not isinstance(row, dict) or not isinstance(row.get('path'), str):
            continue
        try:
            doc = load(local(audit.root, row['path'], True))
        except (ValueError, OSError):
            continue  # governance reports unreadable runs
        if isinstance(doc.get('task'), str) and isinstance(doc.get('started_at'), str):
            result.setdefault(doc['task'], []).append((row['id'], doc['started_at']))
    return result


CHECKPOINTS = {f'CP{i}' for i in range(10)}
STARTED = {'pass', 'conditional', 'waived'}
# Research documents that must carry content once G1 has started (template still = warning).
G1_DOCUMENTS = {'references/EVIDENCE_MAP.md': 'research/EVIDENCE_MAP.md',
                'manuscript/NARRATIVE.md': 'research/NARRATIVE.md'}
TEMPLATES = Path(__file__).resolve().parents[1] / 'assets'


def substantive_lines(text):
    """Lines that carry content: not headers, field labels, empty table cells or placeholders."""
    lines = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(('#', '- **', '|---')):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')] if line.startswith('|') else [line]
        if all(not c or c.endswith(('-', '：', ':')) or c in {'—', '计划', 'v0'} for c in cells):
            continue
        lines.add(line)
    return lines


def still_template(root, relative, template):
    """True when every content line matches a template line ({{...}} treated as wildcards)."""
    path = root / relative
    if not path.is_file():
        return False
    filled = substantive_lines(path.read_text(encoding='utf-8'))
    patterns = [re.compile('^' + '.*'.join(map(re.escape, re.split(r'\{\{[A-Z_]+\}\}', line))) + '$')
                for line in substantive_lines((TEMPLATES / template).read_text(encoding='utf-8'))]
    return all(any(p.match(line) for p in patterns) for line in filled)


def checkpoint_and_template_checks(audit, state, hypotheses):
    decisions = [r for r in state.get('decisions', []) if isinstance(r, dict)]
    for row in decisions:
        checkpoint = row.get('checkpoint')
        if checkpoint is not None and checkpoint not in CHECKPOINTS:
            audit.error(f"{row.get('id')}: checkpoint must be CP0-CP9")
        if row.get('checkpoint_outcome') == 'skipped' and not audit.nonempty(row.get('rationale')):
            audit.error(f"{row.get('id')}: a skipped checkpoint needs a rationale")
    if state.get('project', {}).get('profile') != 'research':
        return
    gates = {g.get('id'): g for g in state.get('gates', []) if isinstance(g, dict)}
    g1_started = gates.get('G1', {}).get('status') in STARTED
    if g1_started:
        for relative, template in G1_DOCUMENTS.items():
            if still_template(audit.root, relative, template):
                audit.warnings.append(f'{relative} is still the blank template although G1 has started; '
                           'fill the CP2 content or record why it is empty')
    # Run folders on disk that the state does not know about (formal runs done outside run_project.py).
    registered = {str(r.get('path', '')).split('/')[1] for r in state.get('runs', [])
                  if isinstance(r, dict) and str(r.get('path', '')).startswith('runs/')}
    on_disk = sorted(p.name for p in (audit.root / 'runs').glob('RUN-*') if p.is_dir()) \
        if (audit.root / 'runs').is_dir() else []
    unregistered = [name for name in on_disk if name not in registered]
    if unregistered:
        audit.warnings.append('Run folders exist on disk but are not registered in state runs: '
                              + ', '.join(unregistered) + '; register them so gates and impacts can see them')
    selected = [h for h, r in hypotheses.items() if r.get('status') in {'prioritized', 'testing', 'supported', 'refuted'}]
    later = any(gates.get(g, {}).get('status') in STARTED for g in ('G2', 'G3')) or bool(on_disk) \
        or bool(state.get('runs'))
    has_cp3 = any(r.get('checkpoint') == 'CP3' for r in decisions)
    if (selected or later) and not has_cp3:
        audit.warnings.append('A hypothesis or analysis route has been chosen but no decision records CP3; '
                   'run a tournament or record the skip with its rationale')


def validate(audit, tasks):
    state = audit.state
    artifacts = {r.get('id'): r for r in state.get('artifacts', []) if isinstance(r, dict)}
    present = [key for key in ('questions', 'hypotheses') if key in state]
    for key in present:
        if not isinstance(state[key], list):
            audit.error(f'{key}: expected a list')
    questions = audit.index('questions', Q_STATUSES) if 'questions' in present and isinstance(state['questions'], list) else {}
    hypotheses = audit.index('hypotheses', H_STATUSES) if 'hypotheses' in present and isinstance(state['hypotheses'], list) else {}
    findings = {r.get('id') for r in state.get('findings', []) if isinstance(r, dict)}
    claims = {r.get('id'): r for r in state.get('claims', []) if isinstance(r, dict)}
    decisions = {r.get('id') for r in state.get('decisions', []) if isinstance(r, dict)}

    parents = {}
    for identity, row in questions.items():
        if not audit.nonempty(row.get('statement')):
            audit.error(f'{identity}: missing statement')
        clarity = row.get('clarity')
        if type(clarity) is not int or not 0 <= clarity <= 5:
            audit.error(f'{identity}: clarity must be an integer 0-5 (see question-shaping ladder)')
        if row.get('type') is not None and row['type'] not in TYPES:
            audit.error(f'{identity}: unknown study type {row["type"]}')
        parent = row.get('parent')
        if parent is not None:
            if parent not in questions:
                audit.error(f'{identity}: unknown parent question {parent}')
            else:
                parents[identity] = parent
        if row.get('status') == 'answered' and not row.get('claims') and not row.get('findings'):
            audit.error(f'{identity}: answered question needs findings or claims')
        for key, index in (('findings', findings), ('claims', set(claims)), ('decisions', decisions)):
            for value in row.get(key, []) if isinstance(row.get(key, []), list) else []:
                if value not in index:
                    audit.error(f'{identity}.{key}: unknown reference {value}')
    for identity in questions:
        seen, cursor = set(), identity
        while cursor in parents:
            if cursor in seen:
                audit.error(f'{identity}: question tree has a cycle')
                break
            seen.add(cursor)
            cursor = parents[cursor]

    for identity, row in hypotheses.items():
        if not audit.nonempty(row.get('statement')):
            audit.error(f'{identity}: missing statement')
        if row.get('question') not in questions:
            audit.error(f'{identity}: hypothesis must belong to a registered question')
        predictions = row.get('predictions')
        if not isinstance(predictions, list) or not predictions:
            audit.error(f'{identity}: needs at least one discriminating prediction')
        if row.get('origin') not in {'ai', 'human'}:
            audit.error(f'{identity}: origin must be ai or human')
        for value in row.get('findings', []) if isinstance(row.get('findings', []), list) else []:
            if value not in findings:
                audit.error(f'{identity}.findings: unknown reference {value}')
        if row.get('status') in {'supported', 'refuted', 'inconclusive'} and not row.get('findings'):
            audit.error(f'{identity}: a tested hypothesis needs findings as evidence')
        source = row.get('source')
        if isinstance(source, dict) and source.get('ranking'):
            audit.file(source['ranking'], identity + '.source.ranking')
            if not audit.nonempty(row.get('decision')) or row['decision'] not in decisions:
                audit.error(f'{identity}: tournament-promoted hypothesis needs the CP3 decision (D-*)')
        independence(audit, identity, row, artifacts)

    checkpoint_and_template_checks(audit, state, hypotheses)

    for gate in state.get('gates', []) if isinstance(state.get('gates'), list) else []:
        # Mixed projects may scope a gate (e.g. a second ethics gate) to one sub-question.
        if isinstance(gate, dict) and gate.get('question') is not None and gate['question'] not in questions:
            audit.error(f"{gate.get('id', '?')}.question: unknown question {gate['question']}")

    designs = state.get('project', {}).get('designs') if isinstance(state.get('project'), dict) else None
    if designs is not None and (not isinstance(designs, list) or any(d not in TYPES for d in designs)):
        audit.error('project.designs: expected a list of study types from research-types.md')

    nodes = set(questions) | set(hypotheses) | set(claims)
    unlinked = []
    run_tasks = run_starts(audit, state)
    for identity, row in tasks.items():
        intent = row.get('intent')
        if intent is not None:
            if not isinstance(intent, dict) or not all(audit.nonempty(intent.get(k)) for k in ('path', 'written_at', 'sha256')):
                audit.error(f'{identity}.intent: needs path, written_at and sha256 (use research_tree.py task intent)')
            else:
                file = audit.file(intent['path'], identity + '.intent')
                if file and digest(file) != intent['sha256']:
                    audit.error(f'{identity}.intent: brief changed after it was recorded; record a new intent instead of editing')
                for run_id, started in run_tasks.get(identity, []):
                    if started < intent['written_at']:
                        audit.error(f'{identity}.intent: written after {run_id} started; expectations must precede results')
        serves = row.get('serves')
        if serves is None:
            if questions and state.get('project', {}).get('profile') == 'research':
                unlinked.append(identity)
            continue
        if not isinstance(serves, list) or not serves:
            audit.error(f'{identity}.serves: expected a nonempty list of Q/H/CLAIM ids')
            continue
        for value in serves:
            if value not in nodes:
                audit.error(f'{identity}.serves: unknown question/hypothesis/claim {value}')
    if unlinked:
        audit.warnings.append('Research tasks not linked to a question, hypothesis or claim (serves): ' + ', '.join(sorted(unlinked)))

    for identity, row in claims.items():
        basis = row.get('basis')
        if basis is None:
            continue
        if basis not in CLAIM_BASES:
            audit.error(f'{identity}: basis must be data, literature or synthesis')
        elif basis == 'synthesis' and row.get('status') == 'supported' and not audit.nonempty(row.get('reviewed_by')):
            audit.error(f'{identity}: supported synthesis claim needs a named human reviewer (reviewed_by)')

    return {'questions': len(questions), 'hypotheses': len(hypotheses),
            'open_questions': sorted(q for q, r in questions.items() if r.get('status') == 'open'),
            'hypotheses_in_test': sorted(h for h, r in hypotheses.items() if r.get('status') in {'prioritized', 'testing'}),
            'unlinked_research_tasks': sorted(unlinked)}
