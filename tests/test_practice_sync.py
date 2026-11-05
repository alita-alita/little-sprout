import copy
import json
import secrets
import unittest
from test_learning import fixture, finish, NOW, event
from practice import apply_practice_event
from learning import questions, LESSONS, complete
from server import validate


def body(action='start', subject='english', **extra):
    return dict(planId='p1', day=1, subject=subject, action=action, eventId=secrets.token_hex(16), **extra)


class PracticeTests(unittest.TestCase):
    def setUp(self):
        self.state = fixture()
        for subject in ('english', 'chinese', 'math'):
            finish(self.state, subject)
        self.original = copy.deepcopy(self.state['plans'][0]['records']['1']['study'])

    def run_event(self, action='start', subject='english', **extra):
        result = apply_practice_event(self.state, body(action, subject, **extra), NOW)
        validate(self.state)
        self.assertFalse(result['autoChecked'])
        self.assertEqual(self.state['plans'][0]['records']['1']['study'], self.original)
        return result

    def entry(self, subject='english'):
        return self.state['plans'][0]['records']['1']['practice'][subject]

    def test_repeat_wrong_answer_hint_and_no_skip_are_server_graded(self):
        self.run_event()
        entry = self.entry()
        q = questions(LESSONS[entry['lessonId']])[0]
        args = {'roundId': entry['roundId'], 'questionId': q['id']}
        with self.assertRaises(ValueError):
            self.run_event('answer', roundId=entry['roundId'], questionId='w1', answer='🍌')
        self.run_event('answer', answer=next(x for x in q['options'] if x != q['answer']), **args)
        self.run_event('hint', **args)
        self.run_event('answer', answer=q['answer'], **args)
        self.assertFalse(entry['steps'][q['id']]['correct'])
        self.run_event('repeat', transcript='banana', **args)
        self.run_event('repeat', transcript=q['speech'], **args)
        self.assertTrue(entry['steps'][q['id']]['correct'])
        self.assertEqual(entry['steps'][q['id']]['repeat']['attempts'], 2)

    def test_full_round_can_restart_but_unfinished_or_stale_round_cannot(self):
        self.run_event(subject='math')
        entry = self.entry('math')
        with self.assertRaises(ValueError):
            self.run_event(subject='math')
        with self.assertRaises(ValueError):
            self.run_event('hint', 'math', roundId='stale', questionId='q0')
        for q in questions(LESSONS[entry['lessonId']]):
            for answer in q['answer'] if q['kind']=='order' else [q['answer']]:
                self.run_event('answer', 'math', questionId=q['id'], answer=answer, roundId=entry['roundId'])
        self.assertTrue(complete(entry))
        self.run_event(subject='math')
        self.assertEqual(self.entry('math')['roundNumber'], 2)
        self.assertEqual(self.entry('math')['steps'], {})

    def test_historical_completed_lesson_is_replayable_and_incomplete_is_rejected(self):
        self.state['plans'][0].update(status='archived', archivedDate='2026-11-04')
        self.run_event()
        self.state['plans'][0]['records']['1']['study']['chinese']['steps'].pop('w0')
        with self.assertRaises(ValueError):
            self.run_event(subject='chinese')

    def test_old_browser_progress_can_be_imported_once_and_validated(self):
        q = questions(LESSONS['english-1'])[0]
        legacy = {'lessonId':'english-1', 'steps':{q['id']:{'correct':False,'choiceCorrect':True,'repeatRequired':True,'attempts':1,'hinted':True,'order':[]}}}
        self.run_event('import', entry=legacy)
        self.assertEqual(self.entry()['steps']['w0']['lastAnswer'], q['answer'])
        with self.assertRaises(ValueError):
            self.run_event('import', entry=legacy)
        bad = copy.deepcopy(self.state)
        bad['plans'][0]['records']['1']['practice']['english']['steps']['w0']['repeat'] = {'score':100}
        with self.assertRaises(ValueError):
            validate(bad)

    def test_partial_order_is_saved_without_touching_formal_checkin(self):
        record = self.state['plans'][0]['records']['1']
        lesson = LESSONS['math-6']
        record['study']['math'] = {'lessonId':'math-6','steps':{q['id']:{'correct':True,'attempts':0,'hinted':False,'order':q['answer'] if q['kind']=='order' else [],'lastAnswer':q['answer'] if q['kind']!='order' else q['answer'][-1]} for q in questions(lesson)}}
        self.original=copy.deepcopy(record['study'])
        self.run_event(subject='math')
        entry=self.entry('math')
        for q in questions(lesson):
            if q['kind']=='order':
                self.run_event('answer','math',roundId=entry['roundId'],questionId=q['id'],answer=q['answer'][0])
                self.assertEqual(entry['steps'][q['id']]['order'],q['answer'][:1])
                break
            self.run_event('answer','math',roundId=entry['roundId'],questionId=q['id'],answer=q['answer'])


if __name__ == '__main__':
    unittest.main()
