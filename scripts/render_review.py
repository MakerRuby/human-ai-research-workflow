#!/usr/bin/env python3
"""Generate an offline read-only review page; --check detects stale snapshots, never records approval."""
import argparse
import html
import os
from pathlib import Path
from urllib.parse import quote
import sys

from check_project import check_project
from project_io import atomic_json, digest, encoded, load, local, now, state


LABELS = {'draft': '草稿', 'produced': '已生成', 'checked': '已检查', 'accepted': '已接受',
          'stale': '需更新', 'rejected': '未接受', 'pending': '待处理', 'pass': '通过', 'fail': '失败',
          'conditional': '有条件', 'needs_evidence': '需补证据', 'commented': '已评论', 'done': '完成',
          'todo': '待执行', 'doing': '进行中', 'blocked': '受阻', 'open': '未关闭', 'closed': '已关闭',
          'full': '完整范围', 'partial': '部分范围', 'smoke': '小规模试跑', 'supported': '有支持',
          'observed': '已观察', 'under_review': '待核实', 'refuted': '被反驳', 'superseded': '已替代',
          'adopted': '已采用', 'proposed': '提议', 'withdrawn': '已撤回', 'succeeded': '执行成功',
          'failed': '执行失败', 'running': '执行中', 'mitigated': '已缓解', 'retired': '已退出使用',
          'ready': '就绪（生成时）'}


def esc(value):
    return html.escape(str(value), quote=True)


def badge(value):
    tone = ('good' if value in {'pass', 'accepted', 'closed', 'done', 'succeeded', 'ready'} else
            'bad' if value in {'fail', 'failed', 'rejected', 'blocked', 'timed_out'} else
            'warn' if value in {'stale', 'pending', 'open', 'needs_evidence', 'conditional'} else
            'muted' if value in {'retired', 'superseded', 'withdrawn'} else 'neutral')
    return '<span class="badge badge-' + tone + '">' + esc(LABELS.get(value, value)) + '</span>'


def inventory(root, current):
    paths = {'_pm/project-state.json'}
    for name in ('README.md', 'AI_CONTRACT.md'):
        if local(root, name).is_file():
            paths.add(name)
    for file in local(root, '_pm').rglob('*'):
        if file.is_file():
            paths.add(file.relative_to(root).as_posix())
    for row in current.get('artifacts', []):
        paths.add(row['path'])
        retirement = row.get('retirement', {})
        paths.update(retirement[k] for k in ('manifest','snapshot') if isinstance(retirement.get(k), str))
        paths.update(retirement.get('evidence', []))
    for collection in ('checks', 'findings', 'decisions', 'claims', 'review_items', 'reproductions', 'runs'):
        for row in current.get(collection, []):
            for key in ('record', 'path', 'report'):
                if isinstance(row.get(key), str):
                    paths.add(row[key])
            for key in ('evidence', 'locations'):
                paths.update(row.get(key, []))
    for row in current.get('runs', []):
        doc = load(local(root, row['path'], True))
        paths.update(doc.get(k) for k in ('stdout', 'stderr') if isinstance(doc.get(k), str))
        for snap in doc.get('snapshots', []):
            if isinstance(snap, dict):
                paths.update(snap[k] for k in ('source', 'snapshot') if isinstance(snap.get(k), str))
        paths.update(r['path'] for r in doc.get('outputs', []) if isinstance(r, dict) and isinstance(r.get('path'), str))
    releases = local(root, current.get('layout', {}).get('releases', 'releases'))
    if releases.is_dir():
        for file in releases.glob('*/manifest.json'):
            paths.add(file.relative_to(root).as_posix())
            doc = load(local(root, file.relative_to(root).as_posix(), True))
            paths.update((file.parent / r['destination']).relative_to(root).as_posix() for r in doc.get('files', []))
            paths.update((file.parent / r['path']).relative_to(root).as_posix() for r in doc.get('generated_files', []))
    result = {}
    for relative in sorted(paths):
        file = local(root, relative)
        result[relative] = digest(file) if file.is_file() else None
    return result


def render(root, check=False, baseline=None):
    root = Path(root).resolve()
    current = state(root)
    review = current.get('layout', {}).get('review', 'review')
    view = local(root, review + '/index.html')
    snapshot_path = local(root, review + '/snapshot.json')
    if review == '_pm' or '_pm' in Path(review).parts:
        raise ValueError('Generated review directory must be outside _pm')
    if any(local(root, a['path']) in {view, snapshot_path} for a in current.get('artifacts', [])):
        raise ValueError('Generated review paths conflict with registered artifacts')
    if not check and (view.exists() or snapshot_path.exists()):
        if not view.is_file() or not snapshot_path.is_file():
            raise ValueError('Refusing to replace unrelated review files')
        previous = load(snapshot_path)
        if previous.get('mode') != 'read_only_snapshot' or digest(view) != previous.get('view_sha256'):
            raise ValueError('Existing view is unrecognized or modified; preserve it before regenerating')
    source_hashes = inventory(root, current)
    if check:
        snapshot = load(snapshot_path)
        changes = sorted(key for key in source_hashes.keys() | snapshot['files'].keys() if source_hashes.get(key) != snapshot['files'].get(key))
        view_ok = view.is_file() and digest(view) == snapshot.get('view_sha256')
        return {'ok': not changes and view_ok, 'changed_inputs': changes, 'view_intact': view_ok,
                'message': 'Snapshot only; opening a page does not verify freshness or record a review.'}
    baseline_doc = load(local(root, baseline, True)) if baseline else None
    baseline_hashes = baseline_doc.get('files', {}) if baseline_doc else {}
    if not isinstance(baseline_hashes, dict) or (baseline_doc and baseline_doc.get('mode') != 'read_only_snapshot'):
        raise ValueError('Baseline must be a generated snapshot with files mapping')
    changed = sorted(key for key in source_hashes.keys() | baseline_hashes.keys() if source_hashes.get(key) != baseline_hashes.get(key)) if baseline else []
    report = check_project(root, verify_hashes=True)
    generated = now()
    assets = Path(__file__).resolve().parents[1] / 'assets'
    css = (assets / 'review.css').read_text(encoding='utf-8')
    js = (assets / 'review.js').read_text(encoding='utf-8')

    def link(relative, label=None):
        if not relative:
            return '—'
        try:
            path = local(root, relative)
            if not path.is_file():
                return esc(label or relative) + '（尚无文件）'
            href = quote(os.path.relpath(path, view.parent).replace('\\', '/'), safe='/')
            return '<a href="' + esc(href) + '">' + esc(label or relative) + '</a>'
        except (ValueError, OSError):
            return esc(label or relative) + '（路径无效）'

    def links(paths):
        return '<br>'.join(link(path) for path in paths) or '—'

    def refs(values):
        return '<br>'.join(esc(r.get('id', '?')) + ' @ ' + esc(r.get('version', '?')) for r in values if isinstance(r, dict)) or '—'

    def table(headers, rows):
        if not rows:
            return '<p class="empty">暂无登记。空清单不代表工作已完成。</p>'
        return '<div class="tablewrap"><table><thead><tr>' + ''.join('<th>' + esc(h) + '</th>' for h in headers) + '</tr></thead><tbody>' + ''.join(
            '<tr class="searchable">' + ''.join('<td>' + str(c) + '</td>' for c in row) + '</tr>' for row in rows) + '</tbody></table></div>'

    def section(identity, title, content):
        return '<section id="' + identity + '"><h2>' + title + '</h2>' + content + '</section>'

    counts = [(len(current.get('review_items', [])), '登记审阅项'),
              (len(report.get('governance', {}).get('open_changes', [])), '未闭环变更'),
              (len(report.get('stale_artifacts', [])), '过期成果'),
              (len(report.get('governance', {}).get('invalid_or_pending_reproductions', [])), '待处理复现验证')]
    cards = '<div class="cards">' + ''.join('<div><strong>' + str(count) + '</strong><span>' + label + '</span></div>' for count, label in counts) + '</div>'
    overview = '<p>' + links(['README.md', '_pm/BRIEF.md', '_pm/STATUS.md', '_pm/LAYOUT.md', 'AI_CONTRACT.md']) + '</p>'
    overview += table(['关口', '状态', '依据'], [(esc(r['id']), badge(r['status']), links(r.get('evidence', []))) for r in current['gates']])
    overview += '<h3>复现覆盖</h3>' + table(['验证', '状态 / 范围', '版本', '证据与限制'], [
        (esc(r['id']) + '<br>' + esc(r.get('title', '')), badge('stale' if r['status'] == 'pass' and r['id'] in report.get('governance', {}).get('invalid_or_pending_reproductions', []) else r['status']) + ' ' + badge(r.get('scope', '?')),
         refs(r.get('inputs', [])), link(r.get('report')) + '<br>' + esc(r.get('rationale', ''))) for r in current.get('reproductions', [])])
    overview += '<h3>自基线变化</h3>' + ('<p>基线：' + link(baseline) + '。基线代表哪次正式审阅，以项目决策记录为准。</p><ul>' + ''.join('<li>' + link(path) + '</li>' for path in changed) + '</ul>' if baseline else '<p>未指定审阅基线；本页不声称展示“上次审阅后”的全部变化。</p>')
    overview += '<h3>结构检查</h3><p>' + ('未发现已登记记录的不一致。' if report['ok'] else '存在记录不一致，需处理。') + '此检查不证明科学成立、材料真实或完整复现。</p>'
    overview += '<ul>' + ''.join('<li>' + esc(message) + '</li>' for message in report['errors'] + report['warnings']) + '</ul>'
    reviews = table(['事项 / 状态', '需要决定', '建议与备选', '影响与版本', '证据 / 正式答复'], [
        (esc(r['id']) + '<br>' + esc(r['title']) + '<br>' + badge(r['status']), esc(r['question']),
         esc(r['recommendation']) + '<hr>' + esc(r['alternatives']), esc(r['consequences']) + '<br>' + refs(r.get('inputs', [])),
         links(r.get('evidence', [])) + '<hr>' + esc(r.get('response', '尚无正式答复'))) for r in current.get('review_items', [])])
    artifacts = table(['成果 / 状态', '版本 / 文件', '上游', '验收'], [
        (esc(r['id']) + '<br>' + badge(r['status']) + (' '+badge('retired') if r.get('lifecycle') == 'retired' else ''), esc(r['version']) + '<br>' + link(r['path']) + ('<br>'+link(r['retirement']['manifest'],'退出原因与归档') if r.get('lifecycle') == 'retired' else ''), refs(r['depends_on']),
         esc(r.get('acceptance', {}).get('by', '尚无接受依据')) + '<br>' + esc(r.get('acceptance', {}).get('rationale', ''))) for r in current['artifacts']])
    release_dir = local(root, current.get('layout', {}).get('releases', 'releases'))
    release_rows = []
    if release_dir.is_dir():
        for file in sorted(release_dir.glob('*/manifest.json')):
            doc = load(local(root, file.relative_to(root).as_posix(), True))
            release_rows.append((esc(doc.get('id')), badge(doc.get('mode')), link(file.relative_to(root).as_posix()), link((file.parent / 'README.md').relative_to(root).as_posix())))
    artifacts += '<h3>固定交付包</h3>' + table(['包', '生成时状态', '清单', '入口'], release_rows)
    tasks = table(['任务', '状态', '输入', '输出'], [(esc(r['id']), badge(r['status']), refs(r['inputs']), esc(', '.join(r['outputs']))) for r in current['tasks']])
    tasks += '<p>任务状态、成果验收和科学可信程度分别展示；不计算缺乏依据的统一完成百分比。</p>'
    changes = table(['变更 / 状态', '原因', '处理清单'], [
        (esc(r['id']) + '<br>' + esc(r['title']) + '<br>' + badge(r['status']), esc(r['reason']),
         '<br>'.join(esc(i.get('kind')) + ':' + esc(i.get('id')) + ' / ' + badge(i.get('status')) + ' / ' + esc(i.get('rationale', '')) for i in r.get('items', []))) for r in current.get('changes', [])])
    changes += '<h3>风险与阻塞</h3>' + table(['风险 / 状态', '影响', '责任与下一动作'], [
        (esc(r['id']) + ' ' + esc(r['title']) + '<br>' + badge(r['status']), esc(r['impact']), esc(r['owner']) + '<br>' + esc(r['next_action'])) for r in current.get('risks', [])])
    evidence = table(['发现 / 核实状态', '观察', '解释', '记录 / 证据'], [
        (esc(r['id']) + ' ' + esc(r['title']) + '<br>' + badge(r['status']), esc(r['observation']), esc(r['interpretation']),
         link(r.get('record')) + '<br>' + links(r.get('evidence', []))) for r in current.get('findings', [])])
    evidence += '<h3>结论到正文</h3>' + table(['结论 / 状态', '强度', '结果版本', '使用位置'], [
        (esc(r['id']) + ' ' + esc(r['statement']) + '<br>' + badge(r['status']), esc(r['strength']), refs(r['results']), links(r['locations'])) for r in current.get('claims', [])])
    evidence += '<h3>决策与运行</h3>' + table(['记录', '状态', '依据'], [
        (esc(r['id']) + ' ' + esc(r.get('title', '')), badge(r['status']), link(r.get('record') or r.get('path'))) for r in current.get('decisions', []) + current.get('runs', [])])
    body = ''.join([section('overview', '项目概况', overview), section('reviews', '需要负责人审阅', reviews), section('artifacts', '成果与交付', artifacts),
                    section('tasks', '任务与依赖', tasks), section('changes', '风险与变更', changes), section('evidence', '证据与历史', evidence)])
    document = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + esc(current['project']['name']) + ' · 项目审阅</title><style>' + css + '</style></head><body><header><span class="eyebrow">人与 AI 协作 · 项目审阅</span><h1>' + esc(current['project']['name']) + '</h1><p>生成于 ' + esc(generated) + '（UTC）</p><p class="notice">只读快照。此页面不写入批准、评论或项目记录；正式答复由助手按负责人原意登记。源文件改变后需检查并重新生成。</p></header><main>' + cards + '<nav aria-label="审阅导航"><a href="#overview">概况</a><a href="#reviews">待审事项</a><a href="#artifacts">成果</a><a href="#tasks">任务</a><a href="#changes">风险与变更</a><a href="#evidence">证据</a></nav><label class="search">查找编号、标题或关键词 <input id="search" type="search" placeholder="例如 FIG-003、样本量、未关闭"></label><p id="search-status" aria-live="polite"></p>' + body + '<footer>执行 render_review.py --project &lt;项目&gt; --check 检查快照新鲜度。此页面完全离线，无外部字体、脚本或服务。</footer></main><script>' + js + '</script></body></html>'
    # Generated view is replaceable; authoritative records are never rewritten here.
    view.parent.mkdir(parents=True, exist_ok=True)
    with view.open('w', encoding='utf-8', newline='\n') as output:
        output.write(document)
    snapshot = {'generated_at': generated, 'files': source_hashes, 'view_sha256': digest(view),
                'baseline': baseline, 'check': report, 'mode': 'read_only_snapshot'}
    atomic_json(root, review + '/snapshot.json', snapshot)
    return {'ok': True, 'records_ok': report['ok'], 'view': str(view), 'snapshot': str(snapshot_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--baseline', help='Project-relative snapshot saved after an actual review')
    args = parser.parse_args(argv)
    try:
        result = render(args.project, args.check, args.baseline)
        print(encoded(result))
        return 0 if result['ok'] else 1
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(encoded({'ok': False, 'error': str(error)}))
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
