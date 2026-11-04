"""Authoritative grading, resumable lessons, and validation for autonomous learning."""
import copy
import datetime as dt
import json
from pathlib import Path

CATALOG = json.loads(Path(__file__).with_name('curriculum.json').read_text(encoding='utf-8'))
LESSONS = CATALOG['lessons']
SUBJECTS = {'english', 'chinese', 'math'}

def require(value, message):
    if not value:
        raise ValueError(message)

def questions(lesson):
    return [q for unit in lesson['units'] for q in unit['questions']]

def complete(entry):
    lesson = LESSONS.get(entry.get('lessonId')) if isinstance(entry, dict) else None
    return bool(lesson) and all(entry.get('steps', {}).get(q['id'], {}).get('correct') is True for q in questions(lesson))

def day_complete(plan, day):
    if not plan.get('study') or day < plan['study']['startDay']:
        record = plan['records'].get(str(day), {})
        return all(record.get(slot, {}).get('done') for slot in ['learning', 'sport'])
    entries = plan['records'].get(str(day), {}).get('study', {})
    return all(complete(entries.get(subject, {})) for subject in plan['study']['subjects'])

def ensure_entry(state, plan, day, subject):
    record = plan['records'].setdefault(str(day), {})
    entries = record.setdefault('study', {})
    if subject in entries:
        return entries[subject]
    previous = []
    for pi, other in enumerate(state['plans']):
        for di, other_record in other['records'].items():
            entry = other_record.get('study', {}).get(subject)
            if entry:
                date = dt.date.fromisoformat(other['start']) + dt.timedelta(days=int(di)-1)
                current = dt.date.fromisoformat(plan['start']) + dt.timedelta(days=day-1)
                if date <= current:
                    previous.append((date, pi, int(di), entry))
    previous.sort(key=lambda value: value[:3])
    last = previous[-1][3] if previous else None
    index = min(90, int(last['lessonId'].split('-')[-1]) + (1 if complete(last) else 0)) if last else 1
    entry = {'lessonId': f'{subject}-{index}', 'steps': {}}
    if last and not complete(last):
        entry['steps'] = copy.deepcopy(last['steps'])
        entry['continued'] = True
    entries[subject] = entry
    return entry

def apply_event(state, body, now=None):
    now = now or dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    today = now.date()
    plan = next((p for p in state['plans'] if p['id'] == body.get('planId')), None)
    require(plan is not None, '计划不存在')
    day = body.get('day')
    require(type(day) is int and 1 <= day <= plan['duration'], '学习日期无效')
    require(plan['status'] == 'active' and (today-dt.date.fromisoformat(plan['start'])).days+1 == day, '只能记录今天的学习；此前进度会保留')
    settings = plan.get('study')
    require(settings and day >= settings['startDay'], '这一天还没有启用自主学习')
    subject = body.get('subject')
    require(subject in settings['subjects'], '这个方向不在本期每日目标中')
    state['selectedPlanId'] = plan['id']
    entry = ensure_entry(state, plan, day, subject)
    if body.get('action') == 'open':
        return {'feedback': 'opened', 'autoChecked': day_complete(plan, day)}
    lesson = LESSONS[entry['lessonId']]
    all_questions = questions(lesson)
    question = next((q for q in all_questions if q['id'] == body.get('questionId')), None)
    require(question is not None, '学习单元不存在')
    step = entry['steps'].get(question['id'], {})
    if step.get('correct'):
        return {'feedback': 'already', 'autoChecked': day_complete(plan, day)}
    next_question = next((q for q in all_questions if not entry['steps'].get(q['id'], {}).get('correct')), None)
    require(next_question and next_question['id'] == question['id'], '请按顺序完成当前单元')
    step = entry['steps'].setdefault(question['id'], {'correct': False, 'attempts': 0, 'hinted': False, 'order': []})
    if body.get('action') == 'hint':
        step['hinted'] = True
        step['updatedAt'] = now.isoformat()
        return {'feedback': 'hint', 'autoChecked': False}
    require(body.get('action') == 'answer', '学习操作无效')
    answer = body.get('answer')
    require(isinstance(answer, str) and answer in question['options'], '请选择画面中的一个答案')
    step['lastAnswer'] = answer
    step['updatedAt'] = now.isoformat()
    if question['kind'] == 'order':
        expected = question['answer'][len(step['order'])]
        if answer == expected:
            step['order'].append(answer)
            correct = len(step['order']) == len(question['answer'])
            feedback = 'correct' if correct else 'piece'
        else:
            step['order'] = []
            correct = False
            feedback = 'try'
    else:
        correct = answer == question['answer']
        feedback = 'correct' if correct else 'try'
    if correct:
        step['correct'] = True
        step['completedAt'] = now.isoformat()
    elif feedback == 'try':
        step['attempts'] += 1
        if step['attempts'] >= 2:
            step['hinted'] = True
    if complete(entry):
        entry['completedAt'] = now.isoformat()
    return {'feedback': feedback, 'autoChecked': day_complete(plan, day)}

def validate_study(plan):
    settings = plan.get('study')
    if settings is not None:
        require(isinstance(settings, dict) and settings.get('version') == 1, '自主学习内容版本不支持')
        require(type(settings.get('startDay')) is int and 1 <= settings['startDay'] <= plan['duration'], '自主学习开始日无效')
        subjects = settings.get('subjects')
        require(isinstance(subjects, list) and 1 <= len(subjects) <= 3 and len(set(subjects)) == len(subjects) and all(s in SUBJECTS for s in subjects), '自主学习方向无效')
    for day, record in plan['records'].items():
        entries = record.get('study', {})
        require(isinstance(entries, dict) and len(entries) <= 3, '学习记录格式无效')
        if entries:
            require(settings and int(day) >= settings['startDay'], '学习记录早于启用日期')
        for subject, entry in entries.items():
            require(subject in settings['subjects'] and isinstance(entry, dict), '学习方向无效')
            lesson = LESSONS.get(entry.get('lessonId'))
            require(lesson and lesson['type'] == subject, '课次不存在')
            steps = entry.get('steps')
            qs = {q['id']: q for q in questions(lesson)}
            require(isinstance(steps, dict) and len(steps) <= len(qs), '学习步骤记录无效')
            for qid, step in steps.items():
                require(qid in qs and isinstance(step, dict), '学习问题不存在')
                require(type(step.get('correct')) is bool and type(step.get('attempts')) is int and 0 <= step['attempts'] <= 100000 and type(step.get('hinted')) is bool, '学习结果格式无效')
                q = qs[qid]
                require(isinstance(step.get('order', []), list) and len(step.get('order', [])) <= len(q['options']), '排序进度无效')
                if q['kind'] == 'order':
                    require(step.get('order', []) == q['answer'][:len(step.get('order', []))], '排序结果不匹配')
                    if step['correct']:
                        require(step.get('order') == q['answer'], '排序尚未完成')
                elif step['correct']:
                    require(step.get('lastAnswer') == q['answer'], '答案与完成结果不匹配')
                for field in ['completedAt', 'updatedAt']:
                    require(isinstance(step.get(field, ''), str) and len(step.get(field, '')) <= 60, '学习时间格式无效')
