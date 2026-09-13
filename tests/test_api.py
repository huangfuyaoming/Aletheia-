"""Contract tests use an injected deterministic fixture, never a production mock mode."""
import io
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from pathlib import Path
from PIL import Image

from app import create_app
from server.legacy import normalize_result, probability
from server.maintenance import cleanup_expired


class FixturePipeline:
    def __init__(self):
        self.available = True
        self.block = threading.Event()
        self.block.set()
        self.entered = threading.Event()

    def health(self):
        return {'available': self.available, 'state': 'fixture', 'mode': 'test', 'device': 'test'}

    def run(self, image, folder):
        self.entered.set()
        self.block.wait(5)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'heat.png'
        Image.new('RGB', (48, 48), 'white').save(path)
        return {'is_fake': True, 'scores': {'sae_v1': None, 'sae_v2': .84, 'mesorch': .12, 'mesorch_p': .10, 'trufor': .9},
                'votes': {'fake': 3, 'total': 5}, 'degraded': False, 'elapsed_ms': 1,
                'artifacts': [{'path': path, 'kind': 'heatmap', 'model': 'sae_v2'}]}


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.pipeline = FixturePipeline()
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'test-only-secret',
                               'DATA_DIR': root, 'DATABASE': root / 'test.sqlite3', 'LLM_URL': '', 'LLM_MODEL': '',
                               'PUBLIC_ORIGIN': '', 'SESSION_COOKIE_SECURE': False, 'QUEUE_CAPACITY': 1}, self.pipeline)
        self.client = self.app.test_client()
        self.headers = {'X-CSRF-Token': self.client.get('/api/v1/session').json['csrf_token']}

    def tearDown(self):
        self.pipeline.block.set()
        self.app.extensions['jobs'].executor.shutdown(wait=True)
        self.app.extensions['chat'].executor.shutdown(wait=True)
        self.tmp.cleanup()

    def upload(self, name='picture.png', content=None):
        buffer = io.BytesIO()
        Image.new('RGB', (64, 48), 'white').save(buffer, 'PNG')
        return self.client.post('/api/v1/detect', data={'file': (io.BytesIO(content if content is not None else buffer.getvalue()), name)}, headers=self.headers)

    def finish(self, task_id):
        for _ in range(200):
            response = self.client.get(f'/api/v1/tasks/{task_id}')
            if response.json['status'] in ('completed', 'failed'):
                return response.json
            time.sleep(.01)
        self.fail('Job did not finish')

    def test_detection_artifacts_ownership_delete(self):
        response = self.upload('../../picture.png')
        self.assertEqual(response.status_code, 202)
        task_id = response.json['task_id']
        result = self.finish(task_id)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['filename'], 'picture.png')
        self.assertEqual(result['result']['scores']['sae_v2'], .84)
        artifact = result['result']['artifacts'][0]['url']
        response = self.client.get(artifact)
        self.assertEqual(response.status_code, 200)
        response.close()
        other = self.app.test_client(); other.get('/api/v1/session')
        self.assertEqual(other.get(f'/api/v1/tasks/{task_id}').status_code, 404)
        self.assertEqual(other.get(artifact).status_code, 404)
        self.assertEqual(other.get('/api/v1/tasks').json['items'], [])
        self.assertEqual(self.client.delete(f'/api/v1/tasks/{task_id}', headers=self.headers).status_code, 204)
        self.assertEqual(self.client.get(artifact).status_code, 404)
        self.assertFalse((Path(self.tmp.name) / 'tasks' / task_id).exists())

    def test_validation_and_unavailable(self):
        self.assertEqual(self.upload(content=b'<html>not an image</html>').status_code, 415)
        self.assertEqual(self.client.post('/api/v1/detect', headers=self.headers).status_code, 400)
        self.pipeline.available = False
        self.assertEqual(self.upload().status_code, 503)
        self.assertEqual(self.client.get('/api/v1/tasks').json['items'], [])

    def test_queue_is_bounded_and_busy_delete_rejected(self):
        self.pipeline.block.clear()
        response = self.upload(); task_id = response.json['task_id']
        self.pipeline.entered.wait(2)
        self.assertEqual(self.upload().status_code, 429)
        self.assertEqual(self.client.delete(f'/api/v1/tasks/{task_id}', headers=self.headers).status_code, 409)
        self.pipeline.block.set(); self.finish(task_id)

    def test_chat_saved_and_isolated_without_provider(self):
        cid = self.client.post('/api/v1/conversations', headers=self.headers).json['id']
        response = self.client.post(f'/api/v1/conversations/{cid}/messages', json={'content': '世界是真实的吗？'}, headers=self.headers)
        self.assertEqual(response.status_code, 202)
        messages = self.client.get(f'/api/v1/conversations/{cid}').json['messages']
        self.assertEqual(messages[0]['content'], '世界是真实的吗？')
        self.assertEqual(messages[1]['error_code'], 'LLM_NOT_CONFIGURED')
        other = self.app.test_client(); other.get('/api/v1/session')
        self.assertEqual(other.get(f'/api/v1/conversations/{cid}').status_code, 404)
        self.assertEqual(self.client.delete(f'/api/v1/conversations/{cid}', headers=self.headers).status_code, 204)
        self.assertEqual(self.client.get('/api/v1/conversations').json['items'], [])

    def test_csrf_and_origin_still_enforced_without_access_gate(self):
        # The access-key gate was removed; CSRF and Origin checks must remain.
        self.assertEqual(self.client.post('/api/v1/conversations').status_code, 403)
        self.assertEqual(self.client.post('/api/v1/conversations', headers=self.headers | {'Origin': 'https://evil.invalid'}).status_code, 403)
        # A plain visit is enough to use the API: no key, no 401.
        fresh = self.app.test_client()
        self.assertEqual(fresh.get('/api/v1/session').json['authenticated'], True)
        self.assertEqual(fresh.get('/api/v1/tasks').status_code, 200)

    def test_configured_chat_adapter_completes_and_preserves_order(self):
        self.app.config.update(LLM_URL='https://provider.invalid/v1/chat/completions', LLM_MODEL='test-model')
        cid = self.client.post('/api/v1/conversations', headers=self.headers).json['id']
        with patch('urllib.request.urlopen', return_value=io.BytesIO(b'{"choices":[{"message":{"content":"Test reply"}}]}')) as upstream:
            self.client.post(f'/api/v1/conversations/{cid}/messages', json={'content': 'hello'}, headers=self.headers)
            for _ in range(200):
                messages = self.client.get(f'/api/v1/conversations/{cid}').json['messages']
                if len(messages) == 2 and messages[1]['status'] == 'completed': break
                time.sleep(.01)
            self.assertEqual(messages[1]['content'], 'Test reply')
            self.assertEqual([m['sequence'] for m in messages], [1, 2])
            self.assertEqual(upstream.call_count, 1)

    def test_cleanup_only_expired_tasks(self):
        task_id = self.upload().json['task_id']; self.finish(task_id)
        self.app.extensions['db'].execute('UPDATE detection_tasks SET expires_at=? WHERE id=?', ('2000-01-01', task_id))
        result = cleanup_expired(self.app.extensions['db'], Path(self.tmp.name))
        self.assertEqual(result, 1)
        self.assertEqual(self.client.get('/api/v1/tasks').json['items'], [])

    def test_legacy_score_parsing_never_invents_missing_v1(self):
        self.assertEqual(probability('87.35%'), .8734999999999999)
        self.assertIsNone(probability('—'))
        self.assertIsNone(probability(float('nan')))
        folder = Path(self.tmp.name); Image.new('RGB', (5, 5)).save(folder / 'heat.jpg')
        result = normalize_result({'is_fake_bool': False, 'conf_v2': '50.00%', 'conf_trufor': '—',
                                   'heat_v2': 'heat.jpg', 'logic_info': '低风险：1/4 个模型判定为篡改。'}, folder, 1)
        self.assertIsNone(result['scores']['sae_v1'])
        self.assertTrue(result['degraded'])
        self.assertEqual(result['votes'], {'fake': 1, 'total': 4})


if __name__ == '__main__':
    unittest.main()
