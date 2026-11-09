"""Persistent authored lessons, immutable releases and plan assignments."""
import copy
import datetime as dt
import json
import re
import uuid

import course_editor
import course_images
import learning

require = learning.require
WORDS = [('apple', '苹果'), ('banana', '香蕉'), ('orange', '橙子'), ('red', '红色'), ('yellow', '黄色')]


def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS authored_courses (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS course_releases (id TEXT PRIMARY KEY, course TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL, UNIQUE(course, revision))')


def releases(db):
    return {ident: json.loads(payload) for ident, payload in db.execute('SELECT id,payload FROM course_releases')}


def text(value, limit, required=False):
    require(isinstance(value, str) and len(value.strip()) <= limit and (not required or value.strip()), '请填写有效的课程文字')
    return value.strip()


def clean(draft):
    require(isinstance(draft, dict), '课程草稿无效')
    subject = draft.get('type', 'english')
    require(subject in learning.SUBJECTS, '请选择有效学科')
    result = {key: text(draft.get(key), limit, key == 'theme' or subject == 'english') for key, limit in [('theme', 60), ('phase', 60), ('goal', 200)]}
    if subject != 'english':
        result['type'] = subject
        return clean_extra(draft, result)
    for section, count in [('words', 5), ('sentences', 5), ('story', 3)]:
        items = draft.get(section)
        require(isinstance(items, list) and len(items) == count, '英语课程需要5个单词、5个句子和3页故事')
        result[section] = []
        for item in items:
            row = {'en': text(item.get('en'), 60 if section == 'words' else 400), 'cn': text(item.get('cn'), 200)}
            if section == 'words':
                image = item.get('image')
                require(image is None or isinstance(image, str) and re.fullmatch(r'(pic_[a-f0-9]{24}|fruit-[0-4])', image), '图片标识无效')
                row['image'] = image
            else:
                ref = item.get('ref')
                require(type(ref) is int and 0 <= ref < 5, '请选择对应的单词卡')
                row.update(ref=ref, review=item.get('review') is True)
            result[section].append(row)
    return result


MATH_TYPES = {'count': '数一数', 'compare': '比大小', 'pattern': '找规律', 'order': '排序'}


def clean_extra(draft, result):
    if result['type'] == 'math':
        rows = draft.get('problems')
        require(isinstance(rows, list) and len(rows) == 5, '数学课程需要5道挑战')
        result['problems'] = []
        for row in rows:
            kind = row.get('kind')
            require(kind in MATH_TYPES, '请选择数学题型')
            result['problems'].append({'kind': kind, **{
                key: text(row.get(key, ''), limit)
                for key, limit in [('prompt', 120), ('symbol', 8), ('left', 2), ('right', 2),
                                   ('direction', 8), ('sequence', 80), ('choices', 80), ('answer', 16)]
            }})
        return result
    for section, count in [('words', 5), ('sentences', 5), ('story', 3)]:
        rows = draft.get(section)
        require(isinstance(rows, list) and len(rows) == count, '汉字课需要5张字卡、5句短句和3页场景')
        result[section] = []
        for row in rows:
            item = {'cn': text(row.get('cn'), 1 if section == 'words' else 200),
                    'cue': text(row.get('cue', ''), 12), 'other': text(row.get('other', ''), 1)}
            if section != 'words':
                ref = row.get('ref')
                require(type(ref) is int and 0 <= ref < 5, '请选择目标字卡')
                item['ref'] = ref
            result[section].append(item)
    return result


def options_from(value):
    return [part.strip() for part in re.split('[,，]', value) if part.strip()]


def quantity(value):
    require(value.isascii() and value.isdigit() and 1 <= int(value) <= 10, '物品数量请填1至10')
    return int(value)


def math_question(row, index):
    kind = row['kind']
    prompt = row['prompt']
    require(prompt, f'第{index + 1}题需要填写题目')
    question = dict(id=f'm{index}', kind='choice', lang='zh-CN', ability=MATH_TYPES[kind],
                    prompt=prompt, speech=prompt, hint='再观察一下，可以重新试一试。')
    if kind == 'count':
        count = quantity(row['left'])
        choices = options_from(row['choices'])
        require(all(choice in {str(n) for n in range(1, 11)} for choice in choices), '数数题选项请填写1至10的数字')
        question.update(display=' '.join([row['symbol'] or '🍎'] * count), options=choices, answer=str(count))
    elif kind == 'compare':
        left, right = quantity(row['left']), quantity(row['right'])
        direction = row['direction']
        require(left != right and direction in ('more', 'less'), '比较题需要两组不同数量，并选择比较方向')
        symbol = row['symbol'] or '🍎'
        question.update(display=f"左边 {' '.join([symbol]*left)}　右边 {' '.join([symbol]*right)}",
                        options=['左边', '右边'], answer='左边' if (left > right) == (direction == 'more') else '右边')
    elif kind == 'pattern':
        sequence = options_from(row['sequence'])
        require(2 <= len(sequence) <= 8, '规律题需要2至8个图案')
        question.update(display='  '.join(sequence + ['？']), options=options_from(row['choices']), answer=row['answer'])
    else:
        direction = row['direction']
        require(direction in ('asc', 'desc'), '请选择排序方向')
        order = ['小圆', '中圆', '大圆']
        question.update(kind='order', display='按顺序点圆形', options=['中圆', '大圆', '小圆'],
                        sizes=dict(zip(order, [24, 48, 75])), answer=order if direction == 'asc' else order[::-1],
                        editableOrder=True)
        return question
    options = question['options']
    require(2 <= len(options) <= 4 and len(set(options)) == len(options) and question['answer'] in options,
            '每题需要2至4个不同选项，且包含正确答案')
    return question


def compile_extra(draft, course):
    subject = draft['type']
    lesson = dict(id=course, courseId=course, type=subject, index=1, stage=1,
                  theme=draft['theme'], phase=draft['phase'] or '亲子自编', goal=draft['goal'], units=[])
    if subject == 'math':
        for index, row in enumerate(draft['problems']):
            question = math_question(row, index)
            lesson['units'].append(dict(id=f'm{index}', section='thinking', label=MATH_TYPES[row['kind']], questions=[question]))
        return lesson
    chars = [row['cn'] for row in draft['words']]
    require(len(set(chars)) == 5 and all(len(char) == 1 and '\u3400' <= char <= '\u9fff' for char in chars),
            '请填写5个不同的汉字')
    story = []
    for section, prefix in [('words', 'w'), ('sentences', 's'), ('story', 'p')]:
        for index, row in enumerate(draft[section]):
            target = chars[index if section == 'words' else row['ref']]
            require(target in row['cn'], f'第{index + 1}条内容需要包含目标字「{target}」')
            other = row['other'] or chars[(chars.index(target) + 1) % 5]
            require(other != target and '\u3400' <= other <= '\u9fff', '干扰字须为另一个汉字')
            question = dict(id=f'{prefix}{index}', kind='story' if section == 'story' else 'choice',
                            prompt='听一听，找出目标字。', display=row['cn'], speech=row['cn'], lang='zh-CN',
                            options=[other, target] if index % 2 else [target, other], answer=target,
                            cue=row['cue'] or target, hint=f'再听一遍，找找「{target}」。')
            if section == 'story':
                if row['cue']:
                    question['scene'] = row['cue']
                story.append(question)
            else:
                lesson['units'].append(dict(id=question['id'], section=section, label=row['cn'], questions=[question]))
    lesson['units'].append(dict(id='story', section='story', label=draft['theme'], questions=story))
    lesson['optionWords'] = {
        char: char for question in learning.questions(lesson) for char in question['options']
    }
    return lesson


def picture(ident):
    if ident.startswith('fruit-'):
        slot = int(ident[-1])
        return {'word': WORDS[slot][0], 'lang': 'en-US', 'atlas': slot}
    return course_images.asset(ident, approved=True)


def compile_lesson(draft, course):
    if draft.get('type', 'english') != 'english':
        return compile_extra(draft, course)
    words = draft['words']
    require(all(row['en'] and row['cn'] for section in ('words', 'sentences', 'story') for row in draft[section]), '请先补齐单词、句子与故事的内容')
    require(len({word['en'].casefold() for word in words}) == 5, '5张单词卡需要不同的单词')
    require(not any(row['review'] for section in ('sentences', 'story') for row in draft[section]), '请先检查受单词修改影响的句子与故事')
    images = {}
    for word in words:
        ident = word['image']
        require(ident, '请为每张单词卡确认配图')
        asset = picture(ident)
        require(asset['lang'] == 'en-US' and asset['word'].casefold() == word['en'].casefold(), '配图与单词不匹配，请重新确认图片')
        images[ident] = asset

    lesson = copy.deepcopy(learning.LESSONS['english-1'])
    lesson.update(id=course, courseId=course, theme=draft['theme'], phase=draft['phase'], goal=draft['goal'],
                  images=images, optionWords={word['image']: word['en'] for word in words})
    for section, prefix in [('words', 'w'), ('sentences', 's'), ('story', 'p')]:
        for index, row in enumerate(draft[section]):
            ref = index if section == 'words' else row['ref']
            answer = words[ref]['image']
            other = words[(ref + 1) % 5]['image']
            unit = lesson['units'][index if section == 'words' else index + 5 if section == 'sentences' else 10]
            question = unit['questions'][index if section == 'story' else 0]
            question.update(id=f'{prefix}{index}', display=row['en'], speech=row['en'], answer=answer,
                            options=[other, answer] if index % 2 else [answer, other],
                            hint='再听一遍，想想刚才说到了什么。')
            if section == 'story':
                question.pop('scene', None)
                question['sceneOptions'] = [word['image'] for word in words[:3]]
                unit['label'] = draft['theme'] + '的小故事'
            else:
                unit['label'] = row['en']
            if section == 'words':
                question['cue'] = answer
    return lesson


def summary(db):
    latest = {}
    for course, ident in db.execute('SELECT course,id FROM course_releases ORDER BY revision'):
        latest[course] = ident
    return [{'id': ident, 'theme': json.loads(payload)['theme'], 'type': json.loads(payload).get('type', 'english'), 'publishedId': latest.get(ident)}
            for ident, payload in db.execute('SELECT id,payload FROM authored_courses ORDER BY rowid DESC')]


def get(db, ident):
    row = db.execute('SELECT revision,payload FROM authored_courses WHERE id=?', (ident,)).fetchone()
    require(row, '课程不存在')
    revision, payload = row
    draft = json.loads(payload)
    published = db.execute('SELECT id,revision FROM course_releases WHERE course=? ORDER BY revision DESC LIMIT 1', (ident,)).fetchone()
    lesson, audio, problem = None, None, ''
    try:
        lesson = compile_lesson(draft, ident)
        audio = course_editor.readiness(lesson) if lesson['type'] == 'english' else None
    except ValueError as error:
        problem = str(error)
    draft_images = {}
    for word in draft.get('words', []):
        if word.get('image'):
            try:
                draft_images[word['image']] = picture(word['image'])
            except ValueError:
                pass
    state = json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
    assignments = [item for item in state.get('courseAssignments', [])
                   if item['entry']['lessonId'].rsplit('-v', 1)[0] == ident]
    return {'id': ident, 'revision': revision, 'assignments': assignments, 'draftImages': draft_images, 'draft': draft, 'lesson': lesson, 'audio': audio, 'problem': problem,
            'publishedId': published[0] if published else None, 'publishedRevision': published[1] if published else None,
            'imageService': course_images.status()}


def assign(db, plan_id, lesson_id):
    revision, payload, previous_updated = db.execute('SELECT revision,payload,updated FROM state WHERE id=1').fetchone()
    state = json.loads(payload)
    plan = next((p for p in state['plans'] if p['id'] == plan_id), None)
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    require(plan and plan['status'] == 'active' and today < dt.date.fromisoformat(plan['start']) + dt.timedelta(days=plan['duration'])
            and 'english' in (plan.get('study') or {}).get('subjects', []), '请选择一份待开始或进行中、包含自主英语学习的计划')
    used = {record.get('study', {}).get('english', {}).get('lessonId') for record in plan['records'].values()}
    course = lesson_id.rsplit('-v', 1)[0]
    require(not any(ident and ident.rsplit('-v', 1)[0] == course for ident in used), '孩子在本期已领取这节课。新版本可以发布到课程库，供以后安排。')
    queue = plan.setdefault('courseQueue', [])
    matching = next((i for i, ident in enumerate(queue) if ident.rsplit('-v', 1)[0] == course), None)
    if matching is not None and queue[matching] == lesson_id:
        return plan['name']
    if matching is None:
        require(len(queue) < 90, '本期课程安排已满')
        queue.append(lesson_id)
    else:
        queue[matching] = lesson_id
    updated = dt.datetime.now(dt.timezone.utc).isoformat()
    db.execute('INSERT INTO revisions VALUES (?,?,?) ON CONFLICT (revision) DO UPDATE SET payload=excluded.payload,updated=excluded.updated',
               (revision, payload, previous_updated))
    db.execute('DELETE FROM revisions WHERE revision < ?', (revision - 29,))
    db.execute('UPDATE state SET revision=?,payload=?,updated=? WHERE id=1', (revision + 1, json.dumps(state, ensure_ascii=False), updated))
    return plan['name']


def act(db, body):
    action = body.get('action')
    ident = body.get('id')
    require(isinstance(ident, str) and re.fullmatch(r'custom-[0-9a-f]{32}', ident), '课程标识无效')
    if action == 'create':
        db.execute('INSERT INTO authored_courses VALUES (?,1,?) ON CONFLICT (id) DO NOTHING',
                   (ident, json.dumps(clean(body.get('draft')), ensure_ascii=False)))
        return get(db, ident)
    current = get(db, ident)
    require(type(body.get('revision')) is int and body['revision'] == current['revision'], '草稿已在另一页面更新，请重新打开课程')
    if action == 'save':
        draft = clean(body.get('draft'))
        require(draft.get('type', 'english') == current['draft'].get('type', 'english'), '已建课程不能更改学科')
        changed = db.execute('UPDATE authored_courses SET revision=revision+1,payload=? WHERE id=? AND revision=?',
                             (json.dumps(draft, ensure_ascii=False), ident, current['revision']))
        require(changed.rowcount == 1, '草稿已在另一页面更新，请重新打开课程')
    elif action == 'audio':
        require(current['draft'].get('type', 'english') == 'english', '这节课使用本机中文朗读')
        require(current['lesson'], current['problem'])
        if not current['audio']['ready']:
            with course_editor.LOCK:
                course_editor.generate_audio(course_editor.readiness(current['lesson'])['missing'])
        latest = get(db, ident)
        require(latest['revision'] == current['revision'], '草稿已更新，请重新打开后检查配音')
        return latest
    elif action in ('publish', 'assign', 'reschedule', 'cancel'):
        if current['draft'].get('type', 'english') != 'english':
            return arrange_extra(db, current, body)
        plan_id = body.get('planId')
        if action == 'publish':
            require(current['lesson'], current['problem'])
            require(current['audio']['ready'], '请先补齐课程配音')
            require(body.get('reviewed') is True, '请先确认孩子视角试玩')
            version = f"{ident}-v{current['revision']}"
            lesson = {**current['lesson'], 'id': version, 'audioFiles': current['audio']['files']}
            db.execute('INSERT INTO course_releases VALUES (?,?,?,?) ON CONFLICT (id) DO NOTHING',
                       (version, ident, current['revision'], json.dumps(lesson, ensure_ascii=False)))
        else:
            version = current['publishedId']
            require(version and plan_id, '请先发布课程并选择计划')
        plan_name = assign(db, plan_id, version) if plan_id else None
        return {**get(db, ident), 'assignedPlan': plan_name}
    else:
        raise ValueError('课程操作无效')
    return get(db, ident)


def arrange_extra(db, current, body):
    action, course = body['action'], current['id']
    revision, payload, updated = db.execute('SELECT revision,payload,updated FROM state WHERE id=1').fetchone()
    state = json.loads(payload)
    require(state.get('child'), '请先建立孩子档案')
    assignments = state.setdefault('courseAssignments', [])
    date = body.get('date')
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    if action != 'cancel' and (action != 'publish' or date):
        require(isinstance(date, str) and dt.date.fromisoformat(date).isoformat() == date
                and today <= dt.date.fromisoformat(date) <= today + dt.timedelta(days=365), '请选择今天起一年内的日期')
    if action == 'publish':
        require(current['lesson'], current['problem'])
        require(body.get('reviewed') is True, '请先确认孩子视角试玩')
        version = f"{course}-v{current['revision']}"
        lesson = {**current['lesson'], 'id': version}
        db.execute('INSERT INTO course_releases VALUES (?,?,?,?) ON CONFLICT (id) DO NOTHING',
                   (version, course, current['revision'], json.dumps(lesson, ensure_ascii=False)))
        if not date:
            return get(db, course)
    else:
        version = current['publishedId']
        require(version, '请先发布课程')
    if action in ('reschedule', 'cancel'):
        item = next((item for item in assignments if item['id'] == body.get('assignmentId')
                     and item['entry']['lessonId'].rsplit('-v', 1)[0] == course), None)
        require(item is not None and not item.get('startedAt'), '只能修改尚未开始的安排')
        if action == 'cancel':
            assignments.remove(item)
        else:
            item['date'] = date
            if body.get('useLatest') is True:
                item['entry']['lessonId'] = version
    elif not any(item['date'] == date and item['entry']['lessonId'] == version for item in assignments):
        require(len(assignments) < 500, '课程安排已满')
        assignments.append({'id': uuid.uuid4().hex, 'date': date,
                            'entry': {'lessonId': version, 'steps': {},
                                      'repeatRequired': current['draft']['type'] == 'chinese'}})
    db.execute('INSERT INTO revisions VALUES (?,?,?) ON CONFLICT (revision) DO UPDATE SET payload=excluded.payload,updated=excluded.updated',
               (revision, payload, updated))
    db.execute('DELETE FROM revisions WHERE revision < ?', (revision - 29,))
    db.execute('UPDATE state SET revision=?,payload=?,updated=? WHERE id=1',
               (revision + 1, json.dumps(state, ensure_ascii=False), dt.datetime.now(dt.timezone.utc).isoformat()))
    return {**get(db, course), 'assignedDate': date if action in ('publish', 'assign') else None}
