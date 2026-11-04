import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import secrets
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('learning_server', ROOT / 'server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
import learning as learn

NOW = dt.datetime(2026, 11, 4, 14, tzinfo=dt.timezone(dt.timedelta(hours=8)))

def fixture(start='2026-11-04', subjects=None):
    task = {'id':'sample','type':'english','title':'样例','subtitle':'样例','materials':'无需材料','minutes':5,'steps':['看一看'],'easy':['试一试'],'condition':'参与','tip':'慢慢来','word':''}
    sport = dict(task, id='sport', type='sport')
    plan = {'id':'p1','name':'学习测试','start':start,'duration':14,'status':'active','days':[[task.copy(),sport.copy()] for _ in range(14)],'records':{},'study':{'version':1,'startDay':1,'subjects':subjects or ['english','chinese','math']}}
    return {'version':1,'child':{'name':'测试','avatar':'bear','months':50,'interests':[]},'plans':[plan],'selectedPlanId':'p1'}

def event(subject='english', action='open', question=None, answer=None, day=1):
    return {'planId':'p1','day':day,'subject':subject,'action':action,'questionId':question,'answer':answer}

def finish(state, subject, now=NOW, day=1):
    learn.apply_event(state,event(subject,day=day),now)
    entry=state['plans'][0]['records'][str(day)]['study'][subject]
    for q in learn.questions(learn.LESSONS[entry['lessonId']]):
        answers=q['answer'] if q['kind']=='order' else [q['answer']]
        for answer in answers:
            result=learn.apply_event(state,event(subject,'answer',q['id'],answer,day),now)
        if subject in ['english','chinese']:
            result=learn.apply_event(state,dict(event(subject,'repeat',q['id'],day=day),transcript=q['speech']),now)
    return result

class LearningTests(unittest.TestCase):
    def test_follow_along_required_before_next_and_saved_score_is_validated(self):
        state=fixture(subjects=['english']);learn.apply_event(state,event(),NOW)
        with self.assertRaises(ValueError):learn.apply_event(state,dict(event(action='repeat',question='w0'),transcript='apple'),NOW)
        q=learn.questions(learn.LESSONS['english-1'])[0]
        result=learn.apply_event(state,event(action='answer',question='w0',answer=q['answer']),NOW)
        self.assertEqual(result['feedback'],'repeat');self.assertFalse(result['autoChecked'])
        with self.assertRaises(ValueError):learn.apply_event(state,event(action='answer',question='w1',answer='🍌'),NOW)
        result=learn.apply_event(state,dict(event(action='repeat',question='w0'),transcript='banana'),NOW)
        self.assertEqual(result['feedback'],'repeat-try')
        result=learn.apply_event(state,dict(event(action='repeat',question='w0'),transcript='Apple.'),NOW)
        self.assertEqual(result['score'],100)
        step=state['plans'][0]['records']['1']['study']['english']['steps']['w0'];self.assertEqual(step['repeat']['attempts'],2)
        server.validate(state)
        step['repeat']['score']=99
        with self.assertRaises(ValueError):server.validate(state)

    def test_matching_score_is_not_a_pronunciation_score(self):
        for target,heard,expected in [('Apple.','apple',100),('cat','car',67),('月','山',0),('一','1',100),('目','木',100),('树木长高了。','树木长高了',100)]:
            self.assertEqual(learn.repeat_score(target,heard),expected)

    def test_course_structure_and_eight_thinking_abilities(self):
        for lesson in learn.LESSONS.values():
            if lesson['type'] in ['english','chinese']:
                self.assertEqual([sum(u['section']==s for u in lesson['units']) for s in ['words','sentences','story']],[5,5,1])
                self.assertEqual(len(lesson['units'][-1]['questions']),3)
            else:
                self.assertEqual(len(lesson['units']),5)
        abilities={q['ability'] for n in range(1,9) for q in learn.questions(learn.LESSONS['math-'+str(n)])}
        self.assertEqual(len(abilities),8)
        self.assertEqual([learn.LESSONS['english-'+str(n)]['stage'] for n in [1,2,3]],[0,1,2])

    def test_wrong_answer_hint_and_no_skipping(self):
        state=fixture();learn.apply_event(state,event(),NOW)
        q=learn.questions(learn.LESSONS['english-1'])[0]
        wrong=next(x for x in q['options'] if x!=q['answer'])
        learn.apply_event(state,event(action='answer',question='w0',answer=wrong),NOW)
        step=state['plans'][0]['records']['1']['study']['english']['steps']['w0']
        self.assertEqual(step['attempts'],1);self.assertFalse(step['correct'])
        learn.apply_event(state,event(action='hint',question='w0'),NOW)
        self.assertTrue(step['hinted'])
        with self.assertRaises(ValueError):
            learn.apply_event(state,event(action='answer',question='w1',answer='🍌'),NOW)
        learn.apply_event(state,event(action='answer',question='w0',answer=q['answer']),NOW)
        self.assertFalse(step['correct']);self.assertTrue(step['choiceCorrect'])
        learn.apply_event(state,dict(event(action='repeat',question='w0'),transcript=q['speech']),NOW)
        self.assertTrue(step['correct']);self.assertTrue(step['hinted'])

    def test_all_three_subjects_auto_check_without_sport(self):
        state=fixture()
        self.assertFalse(finish(state,'english')['autoChecked'])
        self.assertFalse(finish(state,'chinese')['autoChecked'])
        self.assertTrue(finish(state,'math')['autoChecked'])
        self.assertTrue(learn.day_complete(state['plans'][0],1))
        self.assertNotIn('sport',state['plans'][0]['records']['1'])
        server.validate(state)

    def test_partial_carries_and_complete_advances(self):
        state=fixture(subjects=['english']);learn.apply_event(state,event(),NOW)
        q=learn.questions(learn.LESSONS['english-1'])[0]
        learn.apply_event(state,event(action='answer',question='w0',answer=q['answer']),NOW)
        learn.apply_event(state,dict(event(action='repeat',question='w0'),transcript=q['speech']),NOW)
        tomorrow=NOW+dt.timedelta(days=1)
        learn.apply_event(state,event(day=2),tomorrow)
        entry=state['plans'][0]['records']['2']['study']['english']
        self.assertEqual(entry['lessonId'],'english-1');self.assertTrue(entry['continued']);self.assertTrue(entry['steps']['w0']['correct'])
        finish(state,'english',tomorrow,2)
        learn.apply_event(state,event(day=3),tomorrow+dt.timedelta(days=1))
        next_entry=state['plans'][0]['records']['3']['study']['english']
        self.assertEqual(next_entry['lessonId'],'english-2');self.assertEqual(next_entry['steps'],{})

    def test_partial_order_is_persisted(self):
        state=fixture(subjects=['math'])
        # A later course starts with an order challenge after earlier abilities.
        learn.apply_event(state,event('math'),NOW)
        entry=state['plans'][0]['records']['1']['study']['math']
        entry['lessonId']='math-6'
        q=learn.questions(learn.LESSONS['math-6'])[0]
        self.assertEqual(q['kind'],'order')
        result=learn.apply_event(state,event('math','answer',q['id'],q['answer'][0]),NOW)
        self.assertEqual(result['feedback'],'piece')
        self.assertEqual(entry['steps'][q['id']]['order'],[q['answer'][0]])
        self.assertFalse(entry['steps'][q['id']]['correct'])
        server.validate(state)

    def test_new_plan_continues_completed_course_cursor(self):
        state=fixture(subjects=['english'])
        finish(state,'english')
        state['plans'][0].update(status='archived',archivedDate='2026-11-04')
        next_plan=fixture('2026-11-05',subjects=['english'])['plans'][0]
        next_plan['id']='p2';state['plans'].append(next_plan)
        body=dict(event(),planId='p2')
        learn.apply_event(state,body,NOW+dt.timedelta(days=1))
        self.assertEqual(next_plan['records']['1']['study']['english']['lessonId'],'english-2')
        server.validate(state)

    def test_old_records_and_date_locks(self):
        state=fixture();p=state['plans'][0];p['study']['startDay']=2
        p['records']['1']={'learning':{'done':True,'mode':'standard','time':'','reaction':''},'sport':{'done':True,'mode':'standard','time':'','reaction':''}}
        self.assertTrue(learn.day_complete(p,1))
        with self.assertRaises(ValueError):learn.apply_event(state,event(),NOW)
        with self.assertRaises(ValueError):learn.apply_event(state,event(day=2),NOW)
        p['status']='archived';p['archivedDate']='2026-11-04'
        with self.assertRaises(ValueError):learn.apply_event(state,event(day=2),NOW+dt.timedelta(days=1))

    def test_forged_completion_rejected_in_backup(self):
        state=fixture();learn.apply_event(state,event(),NOW)
        state['plans'][0]['records']['1']['study']['english']['steps']['w0']={'correct':True,'attempts':0,'hinted':False,'lastAnswer':'🚗','order':[]}
        with self.assertRaises(ValueError):server.validate(state)

class EventApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.db=str(Path(self.temp.name)/'test.sqlite3');server.initialize(self.db)
        self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);self.http.db=self.db;self.http.token='test-token'
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.base='http://127.0.0.1:'+str(self.http.server_port)
        start=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat()
        state=fixture(start,subjects=['english'])
        with server.connect(self.db) as c:c.execute('UPDATE state SET payload=? WHERE id=1',(json.dumps(state),))

    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join();self.temp.cleanup()

    def call(self,path='/api/study-event',body=None,method=None):
        req=Request(self.base+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json','X-Sprout-Token':'test-token'},method=method or ('POST' if body else 'GET'))
        try:
            with urlopen(req) as r:return r.status,json.load(r)
        except HTTPError as error:return error.code,json.load(error)

    def test_idempotency_reopen_and_put_cannot_forge_progress(self):
        body=dict(event(),eventId=secrets.token_hex(12),revision=0)
        status,opened=self.call(body=body);self.assertEqual(status,200)
        q=learn.questions(learn.LESSONS['english-1'])[0]
        wrong=next(x for x in q['options'] if x!=q['answer'])
        answer=dict(event(action='answer',question='w0',answer=wrong),eventId=secrets.token_hex(12),revision=opened['revision'])
        status,first=self.call(body=answer);self.assertEqual(status,200)
        status,repeated=self.call(body=answer);self.assertEqual(status,200);self.assertEqual(first['revision'],repeated['revision'])
        step=repeated['state']['plans'][0]['records']['1']['study']['english']['steps']['w0'];self.assertEqual(step['attempts'],1)
        server.initialize(self.db)
        _,after=self.call('/api/state');self.assertEqual(after['state'],repeated['state'])
        forged=copy.deepcopy(after['state']);forged['plans'][0]['records']['1']['study']['english']['steps']['w0'].update(correct=True,lastAnswer=q['answer'])
        status,_=self.call('/api/state',{'state':forged,'revision':after['revision']},'PUT');self.assertEqual(status,400)
        self.assertEqual(self.call('/api/state')[1]['state'],after['state'])
        changed=dict(answer,answer=q['answer'])
        self.assertEqual(self.call(body=changed)[0],400)

    def test_repeat_score_is_saved_idempotently_and_blocks_next_question(self):
        _,opened=self.call(body=dict(event(),eventId=secrets.token_hex(12),revision=0))
        q=learn.questions(learn.LESSONS['english-1'])[0]
        _,answer=self.call(body=dict(event(action='answer',question='w0',answer=q['answer']),eventId=secrets.token_hex(12),revision=opened['revision']))
        self.assertEqual(answer['result']['feedback'],'repeat')
        self.assertEqual(self.call(body=dict(event(action='answer',question='w1',answer='🍌'),eventId=secrets.token_hex(12),revision=answer['revision']))[0],400)
        body=dict(event(action='repeat',question='w0'),transcript='Apple',eventId=secrets.token_hex(12),revision=answer['revision'])
        status,passed=self.call(body=body);self.assertEqual(status,200);self.assertEqual(passed['result']['score'],100)
        _,repeated=self.call(body=body);self.assertEqual(repeated['revision'],passed['revision'])
        server.initialize(self.db);_,saved=self.call('/api/state')
        step=saved['state']['plans'][0]['records']['1']['study']['english']['steps']['w0']
        self.assertTrue(step['correct']);self.assertEqual(step['repeat']['attempts'],1);self.assertEqual(step['repeat']['score'],100)

if __name__=='__main__':unittest.main()
