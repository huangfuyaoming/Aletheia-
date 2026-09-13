import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

log = logging.getLogger(__name__)


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


class DetectionJobs:
    def __init__(self, db, pipeline, config):
        self.db, self.pipeline, self.config = db, pipeline, config
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='inference')
        self.slots = threading.BoundedSemaphore(config['QUEUE_CAPACITY'])
        # No silent re-run on process restart. The persisted history explains interrupted work.
        db.execute("UPDATE detection_tasks SET status='failed', error_code='SERVER_RESTARTED', error_message=?, finished_at=? WHERE status IN ('queued','running')",
                   ('服务重启中断了任务，请重新上传。', now()))

    def submit_reserved(self, task_id):
        try:
            self.executor.submit(self.run, task_id)
        except Exception:
            self.slots.release()
            raise

    def run(self, task_id):
        try:
            row = self.db.one('SELECT * FROM detection_tasks WHERE id=?', (task_id,))
            self.db.execute("UPDATE detection_tasks SET status='running', started_at=? WHERE id=?", (now(), task_id))
            root = self.config['DATA_DIR']
            result = self.pipeline.run(root / row['input_path'], root / 'tasks' / task_id / 'results')
            with self.db.connect() as conn:
                public_artifacts = []
                for artifact in result.pop('artifacts'):
                    path = Path(artifact['path']).resolve()
                    if not path.is_relative_to(root.resolve()):
                        raise ValueError('Artifact outside storage')
                    aid = str(uuid4())
                    mime = 'image/png' if path.suffix.lower() == '.png' else 'image/jpeg'
                    conn.execute('INSERT INTO artifacts VALUES (?,?,?,?,?,?,?)',
                                 (aid, task_id, artifact['kind'], artifact['model'], str(path.relative_to(root)), mime, now()))
                    public_artifacts.append({'id': aid, 'model': artifact['model'], 'kind': artifact['kind'], 'url': f'/api/v1/artifacts/{aid}'})
                result['artifacts'] = public_artifacts
                conn.execute("UPDATE detection_tasks SET status='completed', result_json=?, finished_at=? WHERE id=?",
                             (json.dumps(result, ensure_ascii=False), now(), task_id))
        except Exception:
            log.exception('Detection failed task=%s', task_id)
            self.db.execute("UPDATE detection_tasks SET status='failed', error_code='INFERENCE_FAILED', error_message=?, finished_at=? WHERE id=?",
                            ('模型暂时无法完成鉴别，请联系管理员检查推理日志。', now(), task_id))
        finally:
            self.slots.release()


class ChatJobs:
    def __init__(self, db, config):
        self.db, self.config = db, config
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='chat')
        self.slots = threading.BoundedSemaphore(8)
        db.execute("UPDATE messages SET status='failed',error_code='SERVER_RESTARTED' WHERE status IN ('pending','running')")

    def configured(self):
        return bool(self.config['LLM_URL'] and self.config['LLM_MODEL'])

    def submit_reserved(self, conversation_id, message_id):
        try:
            self.executor.submit(self.run, conversation_id, message_id)
        except Exception:
            self.slots.release()
            raise

    def run(self, conversation_id, message_id):
        from urllib.request import Request, urlopen
        try:
            self.db.execute("UPDATE messages SET status='running' WHERE id=?", (message_id,))
            history = self.db.all("SELECT role,content FROM messages WHERE conversation_id=? AND status='completed' ORDER BY sequence DESC LIMIT 40", (conversation_id,))[::-1]
            system = {'role': 'system', 'content': '你是观真，一个平静、简洁、富有好奇心的中文对话助手。讨论真实与感知。你不能直接看到或鉴别图像；没有检测结果时不得编造置信度或声称完成检测。不要使用玄学结论冒充事实。'}
            body = json.dumps({'model': self.config['LLM_MODEL'], 'messages': [system] + history,
                               'stream': False, 'max_tokens': 1200}).encode()
            headers = {'Content-Type': 'application/json'}
            if self.config['LLM_API_KEY']:
                headers['Authorization'] = 'Bearer ' + self.config['LLM_API_KEY']
            request = Request(self.config['LLM_URL'], data=body, headers=headers, method='POST')
            with urlopen(request, timeout=self.config['LLM_TIMEOUT']) as response:
                output = json.loads(response.read(2 * 1024 * 1024))
            content = output['choices'][0]['message']['content']
            if not isinstance(content, str) or not content.strip():
                raise ValueError('Empty provider response')
            with self.db.connect() as conn:
                conn.execute("UPDATE messages SET content=?,status='completed' WHERE id=?", (content[:24000], message_id))
                conn.execute('UPDATE conversations SET updated_at=? WHERE id=?', (now(), conversation_id))
        except Exception:
            log.exception('Chat provider failed message=%s', message_id)
            self.db.execute("UPDATE messages SET status='failed',error_code='LLM_FAILED',content=? WHERE id=?",
                            ('这一次回应未能抵达，请稍后再试。', message_id))
        finally:
            self.slots.release()
