import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import course_editor as editor
import learning

class CourseEditorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.connection=sqlite3.connect(':memory:')
        catalog=copy.deepcopy(learning.CATALOG)
        self.patches=[patch.object(editor,'ROOT',Path(self.temp.name)),patch.object(learning,'CATALOG',catalog),patch.object(learning,'LESSONS',catalog['lessons']),patch.object(editor,'readiness',return_value={'ready':True,'missing':[],'count':13,'files':{'en-US':{},'zh-CN':{}}})]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.connection.close();self.temp.cleanup()
    def test_draft_roundtrip_conflict_and_immutable_publication(self):
        base='english-1';original=copy.deepcopy(learning.LESSONS[base]);data=editor.get(self.connection,base)
        draft=data['lesson'];draft['theme']='我的水果店';draft['units'][5]['questions'][0]['speech']='I see an apple.'
        saved=editor.act(self.connection,{'id':base,'revision':0,'action':'save','lesson':draft})
        self.assertEqual(saved['revision'],1);self.assertEqual(editor.get(self.connection,base)['lesson']['theme'],'我的水果店')
        with self.assertRaises(ValueError):editor.act(self.connection,{'id':base,'revision':0,'action':'save','lesson':draft})
        published=editor.act(self.connection,{'id':base,'revision':1,'action':'publish'})
        version=published['publishedId'];self.assertNotEqual(version,base);self.assertEqual(learning.LESSONS[base],original)
        self.assertEqual(learning.LESSONS[version]['theme'],'我的水果店')
        state={'plans':[]};plan={'id':'p','start':'2026-11-05','records':{}};state['plans']=[plan]
        entry=learning.ensure_entry(state,plan,1,'english');self.assertEqual(entry['lessonId'],version)
        # An in-progress original lesson remains attached to its original version.
        plan['records']['2']={'study':{'english':{'lessonId':base,'steps':{}}}}
        self.assertEqual(learning.ensure_entry(state,plan,2,'english')['lessonId'],base)
        disk=json.loads((Path(self.temp.name)/'curriculum.json').read_text());self.assertEqual(disk['published'][base],version)
    def test_audio_readiness_blocks_publishing_and_invalid_answers_are_rejected(self):
        data=editor.get(self.connection,'chinese-1');draft=data['lesson'];draft['units'][0]['questions'][0]['answer']='不存在的选项'
        with self.assertRaises(ValueError):editor.validate('chinese-1',draft)
        draft=copy.deepcopy(learning.LESSONS['chinese-1']);editor.act(self.connection,{'id':'chinese-1','revision':0,'action':'save','lesson':draft})
        with patch.object(editor,'readiness',return_value={'ready':False,'missing':[{'text':'新文本','lang':'zh-CN'}],'count':1}):
            with self.assertRaises(ValueError):editor.act(self.connection,{'id':'chinese-1','revision':1,'action':'publish'})
    def test_published_course_cursor_advances_using_index_not_version_suffix(self):
        draft=copy.deepcopy(learning.LESSONS['english-1']);editor.act(self.connection,{'id':'english-1','revision':0,'action':'save','lesson':draft})
        version=editor.act(self.connection,{'id':'english-1','revision':1,'action':'publish'})['publishedId']
        complete={'lessonId':version,'steps':{q['id']:{'correct':True} for q in learning.questions(learning.LESSONS[version])}}
        plan={'id':'p','start':'2026-11-05','records':{'1':{'study':{'english':complete}}}};state={'plans':[plan]}
        self.assertEqual(learning.ensure_entry(state,plan,2,'english')['lessonId'],'english-2')

if __name__=='__main__':unittest.main()
