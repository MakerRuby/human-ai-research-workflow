#!/usr/bin/env python3
"""Build immutable candidate/ready folders from declared artifacts. Never submit or publish."""
import argparse
from pathlib import Path
import re
import sys

from check_project import check_project
from project_io import digest, encoded, load, local, now, state


def package(root, spec, mode='draft'):
    root = Path(root).resolve()
    current = state(root)
    original_state_hash = digest(local(root, '_pm/project-state.json', True))
    if current.get('schema_version') != 2 or mode not in {'draft', 'ready'}:
        raise ValueError('Use schema 2 and draft/ready mode')
    identity = spec.get('id', '')
    if not isinstance(identity, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', identity):
        raise ValueError('Invalid release ID')
    target_relative = current.get('layout', {}).get('releases', 'releases') + '/' + identity
    target = local(root, target_relative)
    if target.exists():
        raise ValueError('Release already exists; create a new ID instead of replacing it')
    artifacts = {row['id']: row for row in current['artifacts']}
    files = spec.get('files')
    if not isinstance(files, list) or not files:
        raise ValueError('Explicit files list is required, including for a draft')
    report = check_project(root, verify_hashes=True)
    blockers = list(report['errors'])
    governance = report.get('governance', {})
    blockers += ['Open change: ' + identity for identity in governance.get('open_changes', [])]
    required_artifacts = spec.get('required_artifacts', [])
    if not isinstance(required_artifacts, list) or not required_artifacts:
        blockers.append('Declare nonempty required_artifacts')
        required_artifacts = []
    gates = {row['id']: row for row in current['gates']}
    required_gates = spec.get('required_gates', [])
    if not isinstance(required_gates, list) or (current['project']['profile'] == 'research' and not required_gates):
        blockers.append('Declare required_gates')
        required_gates = []
    for gate in required_gates:
        if gates.get(gate, {}).get('status') != 'pass':
            blockers.append('Required gate not passed: ' + str(gate))
    for row in current.get('review_items', []):
        if row.get('blocking') is True and row['status'] != 'accepted':
            blockers.append('Blocking review not accepted: ' + row['id'])
    research = current['project']['profile'] == 'research'
    for key in ('title', 'stage', 'journal' if research else 'recipient'):
        if not isinstance(spec.get(key), str) or not spec[key].strip() or '待' in spec[key]:
            blockers.append('Fill actual release ' + key)
    requirements = local(root, spec.get('requirements_record'), True)
    confirmations = spec.get('confirmations', [])
    if not isinstance(confirmations, list):
        raise ValueError('confirmations must be a list')
    confirmation_ids = set()
    for confirmation in confirmations:
        if not isinstance(confirmation, dict):
            raise ValueError('Invalid confirmation record')
        key = confirmation.get('id')
        if key in confirmation_ids:
            raise ValueError('Duplicate confirmation ID')
        confirmation_ids.add(key)
        if confirmation.get('status') not in {'confirmed', 'not_applicable'} or not all(isinstance(confirmation.get(k), str) and confirmation[k].strip() for k in ('by', 'rationale')):
            blockers.append('Unresolved confirmation: ' + str(key))
        evidence = confirmation.get('evidence', [])
        if not isinstance(evidence, list) or not evidence:
            blockers.append('Missing confirmation evidence: ' + str(key))
        for path in evidence:
            local(root, path, True)
    confirmation_categories = ('authors', 'declarations', 'journal_requirements', 'cross_document_consistency') if research else ('delivery_authorization', 'delivery_requirements', 'cross_document_consistency')
    for key in confirmation_categories:
        if key not in confirmation_ids:
            blockers.append('Missing explicit applicability/confirmation: ' + key)
    needed_repros = spec.get('required_reproductions', [])
    if not isinstance(needed_repros, list):
        raise ValueError('required_reproductions must be a list')
    repros = {row['id']: row for row in current['reproductions']}
    invalid_repros = set(governance.get('invalid_or_pending_reproductions', []))
    coverage = set()
    for identity_repro in needed_repros:
        row = repros.get(identity_repro)
        if row is None or row['status'] != 'pass' or row['scope'] != 'full' or identity_repro in invalid_repros:
            blockers.append('Required full reproduction not current/pass: ' + str(identity_repro))
        else:
            comparison_report = load(local(root, row['report'], True))
            compared = {r['expected'] for r in comparison_report.get('results', []) if isinstance(r, dict) and r.get('status') == 'pass'}
            coverage.update(ref['id'] for ref in row['inputs'] if artifacts.get(ref['id'], {}).get('path') in compared)
    critical = spec.get('critical_results', [])
    if not isinstance(critical, list):
        raise ValueError('critical_results must be a list')
    if current['project']['profile'] == 'research' and (not critical or not needed_repros):
        blockers.append('Research ready release needs declared critical_results and full reproductions')
    for identity_artifact in set(critical) | {row['id'] for row in artifacts.values() if row.get('requires_reproduction') is True and row.get('lifecycle') != 'retired'}:
        if identity_artifact not in coverage:
            blockers.append('Critical result lacks declared full reproduction: ' + str(identity_artifact))
        if identity_artifact not in required_artifacts:
            blockers.append('Critical result must be a required artifact: ' + str(identity_artifact))
    entries, destinations = [], set()
    for item in files:
        if not isinstance(item, dict) or item.get('artifact') not in artifacts:
            raise ValueError('Every release file must reference a registered artifact')
        artifact = artifacts[item['artifact']]
        if artifact.get('lifecycle') == 'retired':
            raise ValueError('Retired artifacts cannot enter new release files: ' + artifact['id'])
        if item.get('version') != artifact['version']:
            raise ValueError('Release file version differs from current artifact version')
        destination = item.get('destination')
        if not isinstance(destination, str) or not destination.startswith(('upload/', 'internal_review/')):
            raise ValueError('Use upload/ or internal_review/ for copied release files')
        local(target, destination)
        if destination.casefold() in {d.casefold() for d in destinations}:
            raise ValueError('Duplicate release destination')
        if destination in {'internal_review/verification.json', 'internal_review/state-at-creation.json'} or destination.startswith(('internal_review/reproductions/', 'internal_review/requirements/', 'internal_review/confirmations/')):
            raise ValueError('Reserved internal evidence destination')
        destinations.add(destination)
        source = local(root, artifact['path'], True)
        entries.append({'artifact': artifact['id'], 'version': artifact['version'], 'source': artifact['path'],
                        'destination': destination, 'sha256': digest(source), 'bytes': source.stat().st_size})
        if destination.startswith('upload/') and artifact['id'] not in required_artifacts:
            blockers.append('Uploaded artifact missing from required_artifacts: ' + artifact['id'])
    for identity_artifact in required_artifacts:
        artifact = artifacts.get(identity_artifact)
        if artifact is None or artifact.get('status') != 'accepted' or artifact.get('lifecycle') == 'retired' or identity_artifact in report.get('stale_artifacts', []):
            blockers.append('Required artifact not current/accepted: ' + str(identity_artifact))
    blockers = sorted(set(blockers))
    if mode == 'ready' and blockers:
        raise ValueError('Release is not ready: ' + '; '.join(blockers))
    manifest = {'schema_version': 1, 'id': identity, 'mode': mode, 'title': spec.get('title'),
                'journal': spec.get('journal'), 'recipient': spec.get('recipient'), 'stage': spec.get('stage'), 'created_at': now(),
                'state_sha256': original_state_hash,
                'requirements_record': spec['requirements_record'], 'requirements_sha256': digest(requirements),
                'required_artifacts': required_artifacts, 'critical_results': critical,
                'required_reproductions': needed_repros, 'confirmations': confirmations, 'files': entries,
                'blockers_at_creation': blockers,
                'scope': 'Readiness under declared scope and recorded evidence; no scientific truth, author consent or actual submission is inferred.'}
    # Freeze the actual comparison reports alongside release material without copying large input data.
    supporting = [('internal_review/requirements/' + requirements.name, spec['requirements_record'])]
    for number, confirmation in enumerate(confirmations):
        for count, relative in enumerate(confirmation.get('evidence', [])):
            source = local(root, relative, True)
            supporting.append((f'internal_review/confirmations/{number:03d}-{count:03d}-{source.name}', relative))
    for destination, relative in supporting:
        source = local(root, relative, True)
        destinations.add(destination)
        entries.append({'artifact': None, 'version': None, 'source': relative, 'destination': destination,
                        'sha256': digest(source), 'bytes': source.stat().st_size})
    for reproduction in needed_repros:
        if reproduction in repros and repros[reproduction].get('report'):
            report_source = local(root, repros[reproduction]['report'], True)
            destination = 'internal_review/reproductions/' + reproduction + '.json'
            if destination in destinations:
                raise ValueError('Reserved reproduction report destination')
            destinations.add(destination)
            entries.append({'artifact': None, 'version': None, 'source': repros[reproduction]['report'],
                            'destination': destination, 'sha256': digest(report_source), 'bytes': report_source.stat().st_size})
    # Destination files are new; on failure only the newly created release tree is removed.
    created = False
    try:
        target.mkdir(parents=True, exist_ok=False)
        created = True
        for entry in entries:
            source = local(root, entry['source'], True)
            destination = local(target, entry['destination'])
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source.open('rb') as stream, destination.open('xb') as output:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
            if digest(destination) != entry['sha256'] or digest(source) != entry['sha256']:
                raise ValueError('Source changed while packaging')
        with (target / 'manifest.json').open('x', encoding='utf-8') as output:
            output.write(encoded(manifest))
        with (target / 'README.md').open('x', encoding='utf-8') as output:
            output.write('# ' + str(spec.get('title', identity)) + '\n\n包编号：' + identity + '\n\n生成时状态：' + mode + '\n\n'
                         '拟上传材料：upload/；内部依据：internal_review/；文件与来源版本：manifest.json。\n\n'
                         '本包固定保存生成时的材料。ready 表示声明范围内检查通过；不表示已经投稿。后续修改生成新编号。\n\n'
                         '生成时阻塞：\n' + ('\n'.join('- ' + b for b in blockers) if blockers else '无已登记阻塞。') + '\n')
        local(target, 'internal_review/verification.json').parent.mkdir(parents=True, exist_ok=True)
        with local(target, 'internal_review/verification.json').open('x', encoding='utf-8') as output:
            output.write(encoded(report))
        with local(target, 'internal_review/state-at-creation.json').open('x', encoding='utf-8') as output:
            output.write(encoded(current))
        # Internal metadata has hashes too. manifest itself is the checksum inventory, not a signature.
        manifest['generated_files'] = [{'path': rel, 'sha256': digest(local(target, rel, True))} for rel in
                                       ('README.md', 'internal_review/verification.json', 'internal_review/state-at-creation.json')]
        if digest(local(root, '_pm/project-state.json', True)) != original_state_hash:
            raise ValueError('Project state changed while packaging; retry with one state writer')
        for entry in entries:
            if digest(local(root, entry['source'], True)) != entry['sha256']:
                raise ValueError('Source evidence changed while packaging')
        (target / 'manifest.json').write_text(encoded(manifest), encoding='utf-8')
    except Exception:
        if created and target.is_dir():
            # No recursive shell deletion: this target was exclusively created by this call.
            import shutil
            shutil.rmtree(target)
        raise
    return {'ok': True, 'path': str(target), 'mode': mode, 'blockers': blockers}


def verify_package(root, relative, against_current=False):
    root = Path(root).resolve()
    target = local(root, relative)
    manifest = load(local(target, 'manifest.json', True))
    errors, drift = [], []
    expected = {'manifest.json'}
    for entry in manifest['files']:
        expected.add(entry['destination'])
        path = local(target, entry['destination'], True)
        if digest(path) != entry['sha256']:
            errors.append('Packaged file changed: ' + entry['destination'])
        if against_current:
            source = local(root, entry['source'])
            if not source.is_file() or digest(source) != entry['sha256']:
                drift.append(entry['source'])
    for entry in manifest.get('generated_files', []):
        expected.add(entry['path'])
        if digest(local(target, entry['path'], True)) != entry['sha256']:
            errors.append('Generated package file changed: ' + entry['path'])
    actual = {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}
    if actual != expected:
        errors.append('Package file inventory differs from manifest')
    if against_current and digest(local(root, '_pm/project-state.json', True)) != manifest.get('state_sha256'):
        drift.append('_pm/project-state.json')
    return {'ok': not errors and not drift, 'package_intact': not errors, 'errors': errors,
            'source_drift': sorted(set(drift)), 'mode_at_creation': manifest['mode']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--spec')
    parser.add_argument('--mode', choices=('draft', 'ready'), default='draft')
    parser.add_argument('--verify', help='Project-relative frozen package directory')
    parser.add_argument('--against-current', action='store_true')
    args = parser.parse_args(argv)
    try:
        if bool(args.spec) == bool(args.verify):
            raise ValueError('Choose exactly one of --spec and --verify')
        result = verify_package(args.project, args.verify, args.against_current) if args.verify else package(args.project, load(local(args.project, args.spec, True)), args.mode)
        print(encoded(result))
        return 0 if result['ok'] else 1
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(encoded({'ok': False, 'error': str(error)}))
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
