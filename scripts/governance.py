"""Schema-2 governance validation. Scientific findings and reviews remain evidence claims."""
from pathlib import Path
from project_io import digest, local, load


COLLECTIONS = {
    'findings': {'observed', 'under_review', 'supported', 'refuted', 'superseded'},
    'decisions': {'proposed', 'adopted', 'superseded', 'withdrawn'},
    'changes': {'open', 'blocked', 'closed'},
    'claims': {'draft', 'supported', 'stale', 'withdrawn'},
    'risks': {'open', 'mitigated', 'closed'},
    'review_items': {'pending', 'commented', 'needs_evidence', 'conditional', 'accepted', 'rejected', 'stale'},
    'runs': {'running', 'succeeded', 'failed', 'timed_out', 'interrupted'},
    'reproductions': {'pending', 'running', 'pass', 'fail', 'blocked', 'stale'},
}


def validate(audit, artifacts, tasks, gates, children, impact=None):
    indexes = {key: audit.index(key, statuses) for key, statuses in COLLECTIONS.items()}
    layout = audit.state.get('layout')
    if not isinstance(layout, dict) or not layout:
        audit.error('layout: role-to-directory mapping is required')
    else:
        for role, path in layout.items():
            try:
                if not audit.nonempty(role):
                    raise ValueError('Empty role')
                local(audit.root, path)
            except (ValueError, OSError, RuntimeError) as error:
                audit.error(f'layout.{role}: {error}')

    def required(row, *keys):
        for key in keys:
            if not audit.nonempty(row.get(key)):
                audit.error(f"{row['id']}: missing {key}")

    def references(row, key, index, nonempty=False):
        values = audit.ids(row, key)
        if nonempty and not values:
            audit.error(f"{row['id']}.{key}: cannot be empty")
        for value in values:
            if value not in index:
                audit.error(f"{row['id']}.{key}: unknown reference {value}")
        return values

    def files(row, key, nonempty=False):
        values = audit.ids(row, key)
        if nonempty and not values:
            audit.error(f"{row['id']}.{key}: requires evidence files")
        for value in values:
            audit.file(value, f"{row['id']}.{key}")

    def current_refs(row, key='inputs', require=False):
        refs = audit.version_refs(row, key, artifacts)
        if require and not refs:
            audit.error(f"{row['id']}.{key}: requires versioned references")
        current = bool(refs) and all(ref['id'] not in audit.stale and
                    artifacts[ref['id']].get('version') == ref['version'] and artifacts[ref['id']].get('lifecycle') != 'retired' for ref in refs)
        return refs, current

    invalid_reproductions = []
    run_docs = {}
    for row in indexes['runs'].values():
        file = audit.file(row.get('path'), row['id'])
        if not file:
            continue
        try:
            doc = load(file)
            if doc.get('id') != row['id'] or doc.get('status') != row['status']:
                audit.error(f"{row['id']}: run index and run.json disagree")
            for key in ('started_at', 'purpose', 'cache_policy', 'cwd'):
                if not audit.nonempty(doc.get(key)):
                    audit.error(f"{row['id']}: missing actual run {key}")
            if not isinstance(doc.get('command'), list) or not doc['command'] or any(not isinstance(v, str) for v in doc['command']):
                audit.error(f"{row['id']}: command must be actual argv")
            if row['status'] != 'running' and not audit.nonempty(doc.get('ended_at')):
                audit.error(f"{row['id']}: completed run needs ended_at")
            if row['status'] == 'succeeded' and doc.get('returncode') != 0:
                audit.error(f"{row['id']}: successful run must exit 0")
            if type(doc.get('environment_rebuilt')) is not bool:
                audit.error(f"{row['id']}: environment_rebuilt must be boolean")
            if row['status'] == 'succeeded' and doc.get('integrity_issues'):
                audit.error(f"{row['id']}: successful run has integrity issues")
            for key in ('stdout', 'stderr'):
                audit.file(doc.get(key), f"{row['id']}.{key}")
            snapshots = doc.get('snapshots')
            if not isinstance(snapshots, list) or not snapshots:
                audit.error(f"{row['id']}: missing input/code/config/environment snapshots")
            else:
                roles = {s.get('role') for s in snapshots if isinstance(s, dict) and isinstance(s.get('role'), str)}
                if not {'code', 'config', 'environment'}.issubset(roles):
                    audit.error(f"{row['id']}: missing code/config/environment snapshot roles")
                for snap in snapshots:
                    if not isinstance(snap, dict):
                        audit.error(f"{row['id']}: invalid snapshot")
                        continue
                    snapshot = audit.file(snap.get('snapshot'), row['id'])
                    if snapshot and digest(snapshot) != snap.get('sha256'):
                        audit.error(f"{row['id']}: archived snapshot content changed")
            refs = audit.version_refs(doc, 'inputs', artifacts)
            # Historical successful runs stay historical; source files may legitimately advance.
            run_docs[row['id']] = doc
        except (ValueError, OSError, TypeError, KeyError, AttributeError) as error:
            audit.error(f"{row['id']}: invalid run record: {error}")

    for row in indexes['reproductions'].values():
        required(row, 'title', 'scope')
        if row.get('scope') not in {'full', 'partial', 'smoke'}:
            audit.error(f"{row['id']}: invalid reproduction scope")
        refs, current = current_refs(row, require=True)
        if type(row.get('required')) is not bool:
            audit.error(f"{row['id']}: reproduction.required must be boolean")
        if row['status'] != 'pass':
            invalid_reproductions.append(row['id'])
            if row['status'] in {'fail', 'blocked'}:
                required(row, 'rationale')
            continue
        before = len(audit.errors)
        audit.evidence(row)
        if row.get('scope') != 'full':
            audit.warnings.append(f"{row['id']}: partial/smoke reproduction does not cover full analysis")
        if not current:
            invalid_reproductions.append(row['id'])
            audit.warnings.append(f"{row['id']}: reproduction references historical/stale versions")
        run = run_docs.get(row.get('run'))
        if run is None or run.get('status') != 'succeeded':
            audit.error(f"{row['id']}: pass needs an indexed successful actual run")
        report_file = audit.file(row.get('report'), row['id'])
        if report_file:
            try:
                report = load(report_file)
                if report.get('status') != 'pass' or report.get('run') != row.get('run') or report.get('inputs') != row.get('inputs'):
                    audit.error(f"{row['id']}: comparison report does not match the reproduction")
                if report.get('scope') != row.get('scope'):
                    audit.error(f"{row['id']}: scope differs from comparison report")
                results = report.get('results')
                if not isinstance(results, list) or not results or any(not isinstance(r, dict) or r.get('status') != 'pass' for r in results):
                    audit.error(f"{row['id']}: no passing output comparisons")
                if run and report.get('run_record_sha256') != digest(local(audit.root, indexes['runs'][row['run']]['path'], True)):
                    audit.error(f"{row['id']}: actual run record changed after comparison")
                if run:
                    for snap in run.get('snapshots', []):
                        if snap.get('role') == 'input':
                            continue  # External large inputs are identified by registered artifacts/manifests.
                        source = audit.file(snap.get('source'), row['id'])
                        if source and digest(source) != snap.get('sha256'):
                            current = False
                    expected_refs = {(r['id'], r['version']) for r in run.get('inputs', [])}
                    if not expected_refs.issubset({(r['id'], r['version']) for r in refs}):
                        audit.error(f"{row['id']}: reproduction omits actual run inputs")
                for result in results if isinstance(results, list) else []:
                    if not isinstance(result, dict):
                        continue
                    for prefix in ('expected', 'actual'):
                        file = audit.file(result.get(prefix), row['id'])
                        if file and digest(file) != result.get(prefix + '_sha256'):
                            current = False
                for ref in refs:
                    artifact = artifacts[ref['id']]
                    file = audit.file(artifact.get('path'), row['id'])
                    recorded = report.get('input_hashes', {}).get(ref['id']) if isinstance(report.get('input_hashes'), dict) else None
                    if current and file and digest(file) != recorded:
                        current = False
                if not current:
                    if row['id'] not in invalid_reproductions:
                        invalid_reproductions.append(row['id'])
                    audit.warnings.append(f"{row['id']}: reproduction is not current; rerun or review required")
            except (ValueError, OSError, TypeError, KeyError, AttributeError) as error:
                audit.error(f"{row['id']}: invalid comparison report: {error}")
        if len(audit.errors) > before and row['id'] not in invalid_reproductions:
            invalid_reproductions.append(row['id'])

    for row in indexes['findings'].values():
        required(row, 'title', 'observed_at', 'by', 'observation', 'interpretation')
        audit.file(row.get('record'), row['id'])
        files(row, 'evidence', nonempty=True)
        current_refs(row, require=True)
        references(row, 'decisions', indexes['decisions'])
        references(row, 'changes', indexes['changes'])

    for row in indexes['decisions'].values():
        required(row, 'title')
        audit.file(row.get('record'), row['id'])
        references(row, 'findings', indexes['findings'])
        if row['status'] in {'adopted', 'superseded'}:
            required(row, 'by', 'decided_at', 'authorization')
            files(row, 'evidence', nonempty=True)

    targets = {'artifact': artifacts, 'task': tasks, 'gate': gates, 'review': indexes['review_items'],
               'reproduction': indexes['reproductions'], 'claim': indexes['claims']}
    for row in indexes['changes'].values():
        required(row, 'title', 'opened_at', 'reason')
        sources = references(row, 'sources', artifacts, nonempty=True)
        references(row, 'findings', indexes['findings'])
        decisions = references(row, 'decisions', indexes['decisions'])
        items = row.get('items')
        if not isinstance(items, list) or not items:
            audit.error(f"{row['id']}: change needs impact checklist")
            continue
        seen = set()
        for item in items:
            if not isinstance(item, dict) or item.get('kind') not in targets:
                audit.error(f"{row['id']}: invalid impact item")
                continue
            key = (item['kind'], item.get('id'))
            if key in seen or item.get('id') not in targets[item['kind']]:
                audit.error(f"{row['id']}: duplicate/unknown impact item {key}")
            seen.add(key)
            replacement = item.get('replacement')
            if replacement is not None and (not isinstance(replacement, str) or replacement not in targets[item['kind']]):
                audit.error(f"{row['id']}: unknown replacement target")
            if item.get('status') not in {'pending', 'blocked', 'updated', 'unchanged'}:
                audit.error(f"{row['id']}: invalid impact treatment")
            if row['status'] == 'closed':
                if item.get('status') not in {'updated', 'unchanged'}:
                    audit.error(f"{row['id']}: cannot close an unresolved impact item")
                required(dict(item, id=row['id']), 'rationale')
                files(dict(item, id=row['id']), 'evidence', nonempty=True)
                if item['kind'] == 'artifact' and not audit.nonempty(item.get('version')):
                    audit.error(f"{row['id']}: completed artifact item needs treated version")
        # Open changes must cover the currently registered downstream chain.
        if row['status'] != 'closed':
            affected = audit.descendants(set(sources), children)
            for identity in affected:
                if ('artifact', identity) not in seen:
                    audit.error(f"{row['id']}: impact checklist omits artifact {identity}")
            for identity, task in tasks.items():
                outputs = task.get('outputs', [])
                inputs = task.get('inputs', [])
                linked = isinstance(outputs, list) and any(isinstance(v, str) and v in affected for v in outputs)
                linked = linked or (isinstance(inputs, list) and any(isinstance(v, dict) and v.get('id') in affected for v in inputs))
                if linked and ('task', identity) not in seen:
                    audit.error(f"{row['id']}: impact checklist omits task {identity}")
            gate_children = {identity: [] for identity in gates}
            affected_gates = set()
            check_index = {c['id']: c for c in audit.state.get('checks', []) if isinstance(c, dict) and isinstance(c.get('id'), str)}
            for identity, gate in gates.items():
                for parent in gate.get('depends_on', []) if isinstance(gate.get('depends_on'), list) else []:
                    if isinstance(parent, str) and parent in gate_children:
                        gate_children[parent].append(identity)
                gate_artifacts = gate.get('artifacts', [])
                linked = isinstance(gate_artifacts, list) and any(isinstance(v, str) and v in affected for v in gate_artifacts)
                checks = gate.get('checks', [])
                linked = linked or (isinstance(checks, list) and any(isinstance(v, str) and check_index.get(v, {}).get('artifact') in affected for v in checks))
                if linked:
                    affected_gates.add(identity)
            for identity in audit.descendants(affected_gates, gate_children):
                if ('gate', identity) not in seen:
                    audit.error(f"{row['id']}: impact checklist omits gate {identity}")
            for kind, collection, field in (('reproduction', indexes['reproductions'], 'inputs'), ('claim', indexes['claims'], 'results'), ('review', indexes['review_items'], 'inputs')):
                for identity, target in collection.items():
                    refs = target.get(field, [])
                    if isinstance(refs, list) and any(isinstance(r, dict) and r.get('id') in affected for r in refs):
                        if (kind, identity) not in seen:
                            audit.error(f"{row['id']}: impact checklist omits {kind} {identity}")
        else:
            required(row, 'closed_at', 'by', 'closure_rationale')
            if any(indexes['decisions'].get(d, {}).get('status') not in {'adopted', 'superseded'} for d in decisions):
                audit.error(f"{row['id']}: closed change has undecided decision")

    for row in indexes['claims'].values():
        required(row, 'statement', 'strength')
        _, current = current_refs(row, 'results', require=True)
        files(row, 'locations', nonempty=True)
        references(row, 'findings', indexes['findings'])
        if row['status'] == 'supported' and not current:
            audit.error(f"{row['id']}: supported claim has stale results; mark stale and recheck interpretation")
        if row['status'] == 'supported':
            files(row, 'evidence', nonempty=True)

    for row in indexes['risks'].values():
        required(row, 'title', 'impact', 'next_action', 'owner')

    for row in indexes['review_items'].values():
        if 'blocking' in row and type(row['blocking']) is not bool:
            audit.error(f"{row['id']}: blocking must be boolean")
        required(row, 'title', 'question', 'recommendation', 'alternatives', 'consequences')
        _, current = current_refs(row, require=True)
        files(row, 'evidence', nonempty=True)
        if row['status'] in {'accepted', 'conditional', 'rejected', 'commented', 'needs_evidence'}:
            required(row, 'by', 'response', 'responded_at')
        if row['status'] in {'accepted', 'conditional'} and not current:
            audit.error(f"{row['id']}: accepted/conditional review is for stale versions")

    result = {'open_changes': sorted(r['id'] for r in indexes['changes'].values() if r['status'] != 'closed'),
              'invalid_or_pending_reproductions': sorted(set(invalid_reproductions)),
              'pending_reviews': sorted(r['id'] for r in indexes['review_items'].values() if r['status'] in {'pending', 'needs_evidence', 'conditional', 'stale'}),
              'counts': {key: len(value) for key, value in indexes.items()}}
    if impact and impact in artifacts:
        affected = audit.descendants({impact}, children)
        result['impact'] = {kind: sorted(row['id'] for row in indexes[kind].values() if isinstance(row.get(field), list) and any(
            isinstance(ref, dict) and ref.get('id') in affected for ref in row[field]))
            for kind, field in (('reproductions', 'inputs'), ('claims', 'results'), ('review_items', 'inputs'))}
    return result
