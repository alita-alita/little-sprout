import copy
import unittest
import learning
from test_learning import fixture, event, NOW, finish
from server import validate
from practice import apply_practice_event


class ManualRepeatTests(unittest.TestCase):
    def test_both_languages_complete_without_microphone_and_round_trip_backup(self):
        for subject in ('english', 'chinese'):
            state=fixture(subjects=[subject])
            learning.apply_event(state,event(subject),NOW)
            entry=state['plans'][0]['records']['1']['study'][subject]
            for i,q in enumerate(learning.questions(learning.LESSONS[entry['lessonId']])):
                learning.apply_event(state,event(subject,'answer',q['id'],q['answer']),NOW)
                manual={'method':'parent-score-v1','score':45} if i%2 else {'method':'parent-confirm-v1'}
                result=learning.apply_event(state,dict(event(subject,'repeat',q['id']),**manual),NOW)
                self.assertTrue(entry['steps'][q['id']]['correct'])
                self.assertEqual(entry['steps'][q['id']]['repeat']['transcript'],'')
                validate(copy.deepcopy(state))
            self.assertTrue(result['autoChecked'])

    def test_manual_requires_correct_choice_and_valid_score(self):
        state=fixture(subjects=['english'])
        learning.apply_event(state,event(),NOW)
        with self.assertRaises(ValueError):
            learning.apply_event(state,dict(event(action='repeat',question='w0'),method='parent-confirm-v1'),NOW)
        q=learning.questions(learning.LESSONS['english-1'])[0]
        learning.apply_event(state,event(action='answer',question=q['id'],answer=q['answer']),NOW)
        for score in (None,-1,101,True,80.5,'90'):
            with self.subTest(score=score),self.assertRaises(ValueError):
                learning.apply_event(copy.deepcopy(state),dict(event(action='repeat',question='w0'),method='parent-score-v1',score=score),NOW)
        for score in (0,100):
            target=copy.deepcopy(state)
            learning.apply_event(target,dict(event(action='repeat',question='w0'),method='parent-score-v1',score=score),NOW)
            validate(target)

    def test_practice_manual_result_does_not_change_original_checkin(self):
        state=fixture();finish(state,'english');original=copy.deepcopy(state['plans'][0]['records']['1']['study'])
        base=dict(planId='p1',day=1,subject='english',eventId='manual-round')
        apply_practice_event(state,dict(base,action='start'),NOW)
        q=learning.questions(learning.LESSONS['english-1'])[0]
        base.update(roundId='manual-round',questionId=q['id'])
        apply_practice_event(state,dict(base,action='answer',answer=q['answer']),NOW)
        apply_practice_event(state,dict(base,action='repeat',method='parent-confirm-v1'),NOW)
        validate(state)
        self.assertEqual(original,state['plans'][0]['records']['1']['study'])
