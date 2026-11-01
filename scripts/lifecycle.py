"""Explicit execution control; stopping work never asserts that its objective was achieved."""
from project_io import local, now


TASK_STATUSES = {'todo', 'doing', 'blocked', 'done', 'paused', 'stopped', 'cancelled'}
CONTROLLED_TASK_STATUSES = {'paused', 'stopped', 'cancelled'}
PROJECT_STATUSES = {'active', 'paused', 'stopped'}


def adopted(current, identity):
    row = next((r for r in current.get('decisions', []) if isinstance(r, dict)
                and r.get('id') == identity), None)
    if not row or row.get('status') != 'adopted':
        raise ValueError('Execution control needs an actual adopted decision')
    return row


def control(root, current, by, rationale, evidence, decision=None):
    if not all(isinstance(v, str) and v.strip() for v in (by, rationale)) or not evidence:
        raise ValueError('A transition needs actual --by, --rationale and --evidence')
    for path in evidence:
        local(root, path, must_exist=True)
    if decision is not None:
        adopted(current, decision)
    return {'by': by, 'rationale': rationale, 'evidence': list(evidence), 'at': now(),
            **({'decision': decision} if decision is not None else {})}


def require_active(current, task=None):
    execution = current.get('project', {}).get('execution', {})
    if execution.get('status', 'active') != 'active':
        raise ValueError('Project execution is paused/stopped; record explicit resumption before running')
    if task is not None:
        row = next((r for r in current.get('tasks', []) if isinstance(r, dict) and r.get('id') == task), None)
        if row and row.get('status') in CONTROLLED_TASK_STATUSES:
            raise ValueError('Task execution is paused/stopped/cancelled; explicit resumption is required')


def set_task(row, status, record):
    row.setdefault('status_history', []).append(
        {'status': row.get('status'), **({'record': row['status_record']} if 'status_record' in row else {})})
    row['status'] = status
    row['status_record'] = dict(record, status=status)


def validate(audit, tasks):
    """Only new optional lifecycle fields are checked; old schema-1/2 files remain valid."""
    project = audit.state.get('project')
    if not isinstance(project, dict):
        return
    decisions = {r.get('id'): r for r in audit.state.get('decisions', []) if isinstance(r, dict)}

    def evidence(row, label, need_decision=False):
        if not isinstance(row, dict):
            audit.error(f'{label}: needs a transition record')
            return
        for field in ('by', 'rationale', 'at'):
            if not audit.nonempty(row.get(field)):
                audit.error(f'{label}: missing {field}')
        paths = row.get('evidence')
        if not isinstance(paths, list) or not paths:
            audit.error(f'{label}: needs evidence files')
        else:
            for path in paths:
                audit.file(path, label + '.evidence')
        identity = row.get('decision')
        if need_decision and not audit.nonempty(identity):
            audit.error(f'{label}: needs an adopted decision')
        if identity is not None and decisions.get(identity, {}).get('status') not in {'adopted', 'superseded'}:
            audit.error(f'{label}: control decision has no retained adoption')

    execution = project.get('execution')
    if execution is not None:
        if not isinstance(execution, dict) or execution.get('status') not in PROJECT_STATUSES:
            audit.error('project.execution: invalid execution status')
        else:
            evidence(execution, 'project.execution', need_decision=True)
            if execution['status'] != 'active' and any(t.get('status') == 'doing' for t in tasks.values()):
                audit.error('project.execution: paused/stopped project still has doing tasks')
    if 'objective_achieved' in project:
        value = project['objective_achieved']
        if value is not None and type(value) is not bool:
            audit.error('project.objective_achieved: must be true, false or null')
        if value is not None:
            evidence(project.get('objective_assessment'), 'project.objective_assessment')
    for identity, row in tasks.items():
        record = row.get('status_record')
        if record is not None or row.get('status') in CONTROLLED_TASK_STATUSES:
            evidence(record, identity + '.status_record', row.get('status') in CONTROLLED_TASK_STATUSES)
            if isinstance(record, dict) and record.get('status') != row.get('status'):
                audit.error(f'{identity}: status and transition record disagree')
