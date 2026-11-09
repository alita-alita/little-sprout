import base64
import copy
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import course_images as images
import course_editor as editor
import learning

# Only used as a provider-response fixture in an isolated temporary directory.
PNG=b'\x89PNG\r\n\x1a\n'+b'\x00'*128
class CourseImagesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.patches=[patch.object(images,'ROOT',self.root),patch.dict('os.environ',{'CLOUDFLARE_ACCOUNT_ID':'','CLOUDFLARE_API_TOKEN':''})]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def configure(self):images.configure({'account':'a'*32,'token':'test-token-never-return'})
    def test_credentials_are_private_and_not_exposed(self):
        self.configure();status=images.status();self.assertTrue(status['configured']);self.assertNotIn('test-token',json.dumps(status));self.assertEqual((self.root/'data/image-service.json').stat().st_mode&0o777,0o600)
        with patch.object(images,'urlopen') as network:
            with self.assertRaises(ValueError):images.start({'word':'apple','lang':'invalid','requestId':'valid-request-123'})
            network.assert_not_called()
    def test_missing_configuration_never_calls_provider(self):
        with patch.object(images,'urlopen') as network:
            with self.assertRaisesRegex(ValueError,'配置'):images.start({'word':'apple','lang':'en-US','requestId':'valid-request-123'})
            network.assert_not_called()
    def test_provider_uses_fixed_endpoint_and_decodes_picture(self):
        self.configure()
        response=io.BytesIO(json.dumps({'success':True,'result':{'image':base64.b64encode(PNG).decode()}}).encode())
        with patch.object(images,'urlopen',return_value=response) as network:self.assertEqual(images.generate('pineapple'),PNG)
        req=network.call_args[0][0];self.assertIn('/ai/run/@cf/black-forest-labs/flux-1-schnell',req.full_url);self.assertIn('pineapple',json.loads(req.data)['prompt']);self.assertEqual(json.loads(req.data)['steps'],4)
        with patch.object(images,'urlopen',side_effect=HTTPError(req.full_url,429,'limit',{},None)):
            with self.assertRaisesRegex(ValueError,'上限'):images.generate('apple')
    def test_job_retry_is_idempotent_and_regeneration_preserves_old_asset(self):
        self.configure();gate=threading.Event()
        def generated(word):gate.wait(2);return PNG
        with patch.object(images,'generate',side_effect=generated) as provider:
            body={'word':'apple','lang':'en-US','requestId':'valid-request-123'};a=images.start(body);b=images.start(body);self.assertEqual(a['id'],b['id']);gate.set()
            for _ in range(100):
                result=images.job(a['id'])
                if result['state']!='running':break
                time.sleep(.01)
            self.assertEqual(result['state'],'ready');self.assertEqual(provider.call_count,1);asset=result['asset'];self.assertTrue((self.root/asset['src'].lstrip('/')).is_file())
            c=images.start({**body,'requestId':'new-request-456'})
            for _ in range(100):
                second=images.job(c['id'])
                if second['state']!='running':break
                time.sleep(.01)
            self.assertNotEqual(second['asset']['id'],asset['id']);self.assertTrue(images.asset(asset['id']))
    def test_approval_and_word_binding_survive_validation_and_audio_collection(self):
        a=images.save_asset(PNG,'pineapple','en-US');draft=copy.deepcopy(learning.LESSONS['english-1']);q=draft['units'][0]['questions'][0];old=q['answer'];q['options']=[a['id'],q['options'][1]];q['answer']=a['id'];q['display']=q['speech']='pineapple'
        with self.assertRaisesRegex(ValueError,'确认'):editor.validate('english-1',draft)
        images.approve(a['id']);saved=editor.validate('english-1',draft)
        self.assertEqual(saved['optionWords'][a['id']],'pineapple');self.assertEqual(saved['optionWords'][old],'apple');self.assertIn(('en-US','pineapple'),editor.audio_texts(saved))
        self.assertEqual(saved['images'][a['id']]['src'],a['src']);self.assertEqual(saved['units'][0]['label'],'pineapple')
        q['display']=q['speech']='banana'
        with self.assertRaisesRegex(ValueError,'不一致'):editor.validate('english-1',draft)
    def test_untrusted_asset_metadata_and_paths_cannot_be_published(self):
        with self.assertRaises(ValueError):images.asset('../../secret')
        a=images.save_asset(PNG,'山','zh-CN');images.approve(a['id']);draft=copy.deepcopy(learning.LESSONS['english-1']);draft['units'][0]['questions'][0]['options'][0]=a['id']
        with self.assertRaisesRegex(ValueError,'语言'):editor.validate('english-1',draft)

if __name__=='__main__':unittest.main()
