"""Server-graded replay rounds, kept separate from formal check-ins."""
import copy
import datetime as dt
from learning import SUBJECTS, LESSONS, questions, complete, grade_entry, validate_study, require


def target(state, body):
    plan = next((p for p in state['plans'] if p['id'] == body.get('planId')), None)
    require(plan is not None, '复习计划不存在')
    day, subject = body.get('day'), body.get('subject')
    require(type(day) is int and 1 <= day <= plan['duration'], '复习日期无效')
    require(subject in SUBJECTS, '复习方向无效')
    record = plan['records'].get(str(day), {})
    original = record.get('study', {}).get(subject, {})
    require(complete(original), '完成这一课后才能复习')
    return plan, record, original


def apply_practice_event(state, body, now=None):
    now = now or dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    plan, record, original = target(state, body)
    subject, action = body['subject'], body.get('action')
    entries = record.setdefault('practice', {})
    entry = entries.get(subject)
    if action in ('start', 'import'):
        require(not entry or complete(entry), '还有未完成的复习，请先接着做')
        require(action != 'import' or entry is None, '已有云端复习进度，请先读取')
        number = entry.get('roundNumber', 1) + 1 if entry else 1
        entry = {'lessonId': original['lessonId'], 'steps': {},
                 'repeatRequired': subject in ('english', 'chinese'),
                 'roundId': body['eventId'], 'roundNumber': number,
                 'createdAt': now.isoformat()}
        if action == 'import':
            legacy = body.get('entry')
            require(isinstance(legacy, dict) and legacy.get('lessonId') == original['lessonId'], '旧复习课次不匹配')
            steps = legacy.get('steps')
            require(isinstance(steps, dict), '旧复习进度无效')
            entry['steps'] = copy.deepcopy(steps)
            # Old browser-only rounds did not store lastAnswer or timestamps.
            for q in questions(LESSONS[original['lessonId']]):
                step = entry['steps'].get(q['id'])
                if not isinstance(step, dict):
                    continue
                if step.get('correct') or step.get('choiceCorrect'):
                    step['lastAnswer'] = q['answer'] if q['kind'] != 'order' else q['answer'][-1]
                step.setdefault('updatedAt', now.isoformat())
                if step.get('correct'):
                    step.setdefault('completedAt', now.isoformat())
            if complete(entry):
                entry['completedAt'] = now.isoformat()
        entries[subject] = entry
        validate_practice(plan)
        return {'feedback': 'started', 'autoChecked': False}
    require(entry is not None and body.get('roundId') == entry.get('roundId'), '复习轮次已更新，请读取最新进度')
    result = grade_entry(entry, body, subject, now)
    result['autoChecked'] = False
    return result


def validate_practice(plan):
    for day, record in plan['records'].items():
        entries = record.get('practice', {})
        require(isinstance(entries, dict) and len(entries) <= 3, '复习记录格式无效')
        for subject, entry in entries.items():
            require(subject in SUBJECTS and isinstance(entry, dict), '复习方向无效')
            original = record.get('study', {}).get(subject, {})
            require(complete(original) and entry.get('lessonId') == original['lessonId'], '复习记录须对应已完成课程')
            require(isinstance(entry.get('roundId'), str) and 1 <= len(entry['roundId']) <= 80, '复习轮次无效')
            require(type(entry.get('roundNumber')) is int and 1 <= entry['roundNumber'] <= 100000, '复习轮次计数无效')
            require(type(entry.get('repeatRequired')) is bool, '复习跟读设置无效')
            require(entry['repeatRequired'] == (subject in ('english', 'chinese')), '复习跟读要求无效')
            # Reuse the full canonical answer, repeat-score and order validation.
            validate_study({'duration': plan['duration'], 'study': plan['study'],
                            'records': {day: {'study': {subject: entry}}}})
            seen_gap = False
            for q in questions(LESSONS[entry['lessonId']]):
                step = entry['steps'].get(q['id'])
                require(not step or not seen_gap, '复习步骤必须按顺序完成')
                if not step or not step.get('correct'):
                    seen_gap = True
