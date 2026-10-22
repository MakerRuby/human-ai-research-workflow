#!/usr/bin/env python3
"""Retire registered artifacts with immutable archive copies; preserve referenced originals."""
import argparse
import copy
from pathlib import Path
import re
import shutil
import sys

from check_project import Audit
from project_io import atomic_json, digest, encoded, load, local, now, state


def archive(root, spec):
    root = Path(root).resolve()
    current = state(root)
    if current.get('schema_version') != 2:
        raise ValueError('Schema 2 required')
    identity = spec.get('id')
    if not isinstance(identity, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', identity):
        raise ValueError('Invalid archive ID')
    for key in ('by', 'reason', 'disposition'):
        if not isinstance(spec.get(key), str) or not spec[key].strip():
            raise ValueError('Fill actual retirement ' + key)
    if spec['disposition'] not in {'invalid', 'superseded', 'out_of_scope', 'exploratory_unused'}:
        raise ValueError('Declare invalid/superseded/out_of_scope/exploratory_unused')
    evidence = spec.get('evidence')
    if not isinstance(evidence, list) or not evidence:
        raise ValueError('Retirement needs actual evidence files')
    for relative in evidence:
        local(root, relative, True)
    ids = spec.get('artifacts')
    if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Declare unique artifact IDs')
    index = {r['id']:r for r in current['artifacts']}
    if spec.get('replacement') is not None and (not isinstance(spec['replacement'], str) or spec['replacement'] not in index or spec['replacement'] in ids or index[spec['replacement']].get('lifecycle') == 'retired'):
        raise ValueError('Replacement must identify an active, different registered artifact')
    base = current.get('layout', {}).get('archive', 'archive') + '/retired/' + identity
    target = local(root, base)
    if target.exists():
        raise ValueError('Archive exists; use a new ID')
    entries = []
    for number, key in enumerate(ids):
        if key not in index or index[key].get('lifecycle') == 'retired':
            raise ValueError('Unknown/already retired artifact: ' + key)
        row = index[key]
        source = local(root, row['path'], True)
        relative = f'files/{number:03d}-{source.name}'
        entries.append({'id':key, 'version':row['version'], 'source':row['path'], 'file':relative, 'sha256':digest(source)})
        row.update(lifecycle='retired', retirement={
            'by':spec['by'], 'reason':spec['reason'], 'disposition':spec['disposition'], 'at':now(),
            'manifest':base+'/manifest.json','snapshot':base+'/'+relative,'evidence':evidence,
            'change':spec.get('change'), 'replacement':spec.get('replacement')})
    # Historical records stay linked to originals. Caller must first invalidate active downstream use.
    change_id = spec.get('change')
    if change_id:
        change = next((r for r in current['changes'] if r['id'] == change_id and r['status'] != 'closed'),None)
        if change is None or not set(ids).issubset(set(change.get('sources', []))):
            raise ValueError('Linked change must be open and cover retired source IDs')
    manifest = {'id':identity,'created_at':now(),'action':'retire_with_copy','spec':copy.deepcopy(spec),'files':entries,
                'note':'Referenced originals preserved. Archive copies are historical evidence, not active inputs.'}
    created = False
    try:
        target.mkdir(parents=True, exist_ok=False)
        created = True
        for entry in entries:
            source = local(root, entry['source'], True)
            destination = local(target, entry['file'])
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source.open('rb') as stream, destination.open('xb') as output:
                shutil.copyfileobj(stream, output)
            if digest(destination) != entry['sha256'] or digest(source) != entry['sha256']:
                raise ValueError('Source changed during archiving')
        with (target/'manifest.json').open('x', encoding='utf-8') as output:
            output.write(encoded(manifest))
        with (target/'README.md').open('x', encoding='utf-8') as output:
            output.write('# 退出使用记录 '+identity+'\n\n'+spec['reason']+'\n\n见 manifest.json 的原位置、版本、证据与处置类型。原引用保留，本目录不是当前可用成果。\n')
        report = Audit(root, current, verify_hashes=True).run()
        if not report['ok']:
            raise ValueError('Retirement impact unresolved: '+'; '.join(report['errors']))
        atomic_json(root, '_pm/project-state.json', current)
    except Exception:
        if created:
            shutil.rmtree(target)
        raise
    return {'ok':True,'path':str(target),'retired':ids,'originals_preserved':True}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True)
    parser.add_argument('--spec',required=True)
    args=parser.parse_args(argv)
    try:
        result=archive(args.project,load(local(args.project,args.spec,True)))
        print(encoded(result)); return 0
    except (ValueError,OSError,TypeError,KeyError) as error:
        print(encoded({'ok':False,'error':str(error)})); return 1


if __name__ == '__main__':
    if hasattr(sys.stdout,'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
