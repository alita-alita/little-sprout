"""Authoritative grading, resumable lessons, and validation for autonomous learning."""
import copy
import datetime as dt
import json
import unicodedata
from pathlib import Path

CATALOG = json.loads(Path(__file__).with_name('curriculum.json').read_text(encoding='utf-8'))
LESSONS = CATALOG['lessons']
SUBJECTS = {'english', 'chinese', 'math'}

def repeat_score(target, heard):
    digits=str.maketrans('0123456789','零一二三四五六七八九')
    def norm(value):
        return ''.join(c for c in unicodedata.normalize('NFKC',value).lower().translate(digits) if c.isalnum())
    a,b=norm(target),norm(heard)
    if a=='目' and b=='木' or a=='长' and b in ['常','肠','场','厂']:b=a
    if not a or not b:return 0
    row=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        new=[i]
        for j,y in enumerate(b,1):new.append(min(row[j]+1,new[j-1]+1,row[j-1]+(x!=y)))
        row=new
    return int(100*(1-row[-1]/max(len(a),len(b)))+.5)

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
    entry = {'lessonId': f'{subject}-{index}', 'steps': {}, 'repeatRequired': subject in ['english','chinese']}
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
    if subject in ['english','chinese'] and not complete(entry):
        entry['repeatRequired']=True
    if body.get('action') == 'open':
        return {'feedback': 'opened', 'autoChecked': day_complete(plan, day)}
    result = grade_entry(entry, body, subject, now)
    result['autoChecked'] = day_complete(plan, day)
    return result

def grade_entry(entry, body, subject, now):
    lesson = LESSONS[entry['lessonId']]
    all_questions = questions(lesson)
    question = next((q for q in all_questions if q['id'] == body.get('questionId')), None)
    require(question is not None, '学习单元不存在')
    step = entry['steps'].get(question['id'], {})
    if step.get('correct'):
        return {'feedback': 'already', 'autoChecked': False}
    next_question = next((q for q in all_questions if not entry['steps'].get(q['id'], {}).get('correct')), None)
    require(next_question and next_question['id'] == question['id'], '请按顺序完成当前单元')
    step = entry['steps'].setdefault(question['id'], {'correct': False, 'attempts': 0, 'hinted': False, 'order': []})
    if body.get('action') == 'repeat':
        require(subject in ['english','chinese'] and step.get('choiceCorrect') and step.get('repeatRequired'), '请先选对当前题的答案，再跟读')
        transcript=body.get('transcript')
        require(isinstance(transcript,str) and 0<len(transcript.strip())<=1000, '没有识别到有效内容，请再读一次')
        score=repeat_score(question['speech'],transcript)
        old=step.get('repeat',{})
        step['repeat']={'transcript':transcript.strip(),'score':score,'passed':score>=80,'attempts':old.get('attempts',0)+1,'updatedAt':now.isoformat(),'method':'content-match-v1'}
        step['updatedAt']=now.isoformat()
        if score>=80:
            step['correct']=True
            step['completedAt']=now.isoformat()
            if complete(entry):entry['completedAt']=now.isoformat()
        return {'feedback':'repeat-pass' if score>=80 else 'repeat-try','score':score,'autoChecked':False}
    if body.get('action') == 'hint':
        step['hinted'] = True
        step['updatedAt'] = now.isoformat()
        return {'feedback': 'hint', 'autoChecked': False}
    require(body.get('action') == 'answer', '学习操作无效')
    if step.get('choiceCorrect') and step.get('repeatRequired'):
        return {'feedback':'repeat','autoChecked':False}
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
        if entry.get('repeatRequired') and subject in ['english','chinese']:
            step.update(choiceCorrect=True,repeatRequired=True)
            feedback='repeat'
        else:
            step['correct'] = True
            step['completedAt'] = now.isoformat()
    elif feedback == 'try':
        step['attempts'] += 1
        if step['attempts'] >= 2:
            step['hinted'] = True
    if complete(entry):
        entry['completedAt'] = now.isoformat()
    return {'feedback': feedback, 'autoChecked': False}

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
            require(type(entry.get('repeatRequired',False)) is bool,'跟读设置无效')
            qs = {q['id']: q for q in questions(lesson)}
            require(isinstance(steps, dict) and len(steps) <= len(qs), '学习步骤记录无效')
            for qid, step in steps.items():
                require(qid in qs and isinstance(step, dict), '学习问题不存在')
                require(type(step.get('correct')) is bool and type(step.get('attempts')) is int and 0 <= step['attempts'] <= 100000 and type(step.get('hinted')) is bool, '学习结果格式无效')
                q = qs[qid]
                require(type(step.get('repeatRequired',False)) is bool and type(step.get('choiceCorrect',False)) is bool,'跟读阶段无效')
                if step.get('choiceCorrect'):
                    require(subject in ['english','chinese'] and step.get('lastAnswer')==q['answer'],'选择阶段尚未完成')
                repeat=step.get('repeat')
                if repeat is not None:
                    require(isinstance(repeat,dict) and step.get('repeatRequired') and step.get('choiceCorrect'),'跟读记录无效')
                    require(isinstance(repeat.get('transcript'),str) and 0<len(repeat['transcript'])<=1000,'跟读内容无效')
                    require(type(repeat.get('score')) is int and repeat['score']==repeat_score(q['speech'],repeat['transcript']),'跟读分数无效')
                    require(type(repeat.get('passed')) is bool and repeat['passed']==(repeat['score']>=80),'跟读结果无效')
                    require(type(repeat.get('attempts')) is int and 1<=repeat['attempts']<=100000,'跟读次数无效')
                    require(isinstance(repeat.get('updatedAt'),str) and len(repeat['updatedAt'])<=60,'跟读时间无效')
                if step.get('correct') and step.get('repeatRequired'):
                    require(repeat and repeat.get('passed'),'需要跟读通过才能完成')
                require(isinstance(step.get('order', []), list) and len(step.get('order', [])) <= len(q['options']), '排序进度无效')
                if q['kind'] == 'order':
                    require(step.get('order', []) == q['answer'][:len(step.get('order', []))], '排序结果不匹配')
                    if step['correct']:
                        require(step.get('order') == q['answer'], '排序尚未完成')
                elif step['correct']:
                    require(step.get('lastAnswer') == q['answer'], '答案与完成结果不匹配')
                for field in ['completedAt', 'updatedAt']:
                    require(isinstance(step.get(field, ''), str) and len(step.get(field, '')) <= 60, '学习时间格式无效')
