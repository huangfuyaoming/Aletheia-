import hashlib
import io
import logging
import os
import secrets
import shutil
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, request, send_file, send_from_directory, session
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.exceptions import HTTPException

from server.db import Database, task_public
from server.jobs import ChatJobs, DetectionJobs, now
from server.legacy import LegacyPipeline
from server.settings import ROOT, settings


def create_app(overrides=None, pipeline=None):
    app = Flask(__name__, static_folder=None)
    app.config.update(settings())
    if overrides:
        app.config.update(overrides)
    data = Path(app.config['DATA_DIR']).resolve()
    app.config['DATA_DIR'] = data
    data.mkdir(parents=True, exist_ok=True)
    db = Database(app.config['DATABASE'])
    pipeline = pipeline or LegacyPipeline(app.config)
    jobs = DetectionJobs(db, pipeline, app.config)
    chat = ChatJobs(db, app.config)
    app.extensions.update(db=db, pipeline=pipeline, jobs=jobs, chat=chat)

    def error(code, message, status=400):
        return jsonify(error={'code': code, 'message': message}), status

    def owner():
        return session['visitor_id']

    def owned_task(task_id):
        return db.one('SELECT * FROM detection_tasks WHERE id=? AND owner_id=?', (task_id, owner()))

    def owned_conversation(cid):
        return db.one('SELECT * FROM conversations WHERE id=? AND owner_id=?', (cid, owner()))

    @app.before_request
    def protect():
        if not request.path.startswith('/api/'):
            return None
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('Origin')
            allowed = app.config['PUBLIC_ORIGIN'] or request.host_url.rstrip('/')
            if origin and origin.rstrip('/') != allowed:
                return error('ORIGIN_REJECTED', '请求来源不匹配。', 403)
        if request.path in ('/api/v1/health', '/api/v1/session'):
            return None
        if not session.get('visitor_id'):
            return error('UNAUTHENTICATED', '请刷新页面建立会话。', 401)
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            if not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), session.get('csrf', '!')):
                return error('CSRF_REJECTED', '会话已更新，请刷新页面。', 403)

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(HTTPException)
    def http_error(exc):
        if exc.code == 413:
            return error('FILE_TOO_LARGE', '图片不能超过 10 MB。', 413)
        return error(f'HTTP_{exc.code}', '请求无法处理。', exc.code)

    @app.get('/api/v1/health')
    def health():
        return jsonify(status='ok', inference=pipeline.health(), chat={'available': chat.configured()},
                       retention_days=app.config['RETENTION_DAYS'], max_upload_bytes=app.config['MAX_UPLOAD_BYTES'])

    @app.route('/api/v1/session', methods=['GET', 'POST'])
    def establish_session():
        # No access gate: visiting the page is enough to get a visitor session.
        # Each visitor still only ever sees their own tasks and conversations.
        if not session.get('visitor_id'):
            session['visitor_id'] = str(uuid4())
            session['csrf'] = secrets.token_hex(24)
        session.permanent = True
        db.execute('INSERT INTO visitors VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET last_seen_at=excluded.last_seen_at',
                   (owner(), now(), now()))
        return jsonify(csrf_token=session['csrf'], authenticated=True, visitor_id=owner())

    @app.post('/api/v1/detect')
    def detect():
        if not pipeline.health()['available']:
            return error('MODEL_UNAVAILABLE', '尚未连接服务器模型。图片不会上传，请完成服务器配置后再试。', 503)
        file = request.files.get('file')
        if not file or not file.filename:
            return error('FILE_REQUIRED', '请选择一张图片。')
        raw = file.stream.read(app.config['MAX_UPLOAD_BYTES'] + 1)
        if len(raw) > app.config['MAX_UPLOAD_BYTES']:
            return error('FILE_TOO_LARGE', '图片大小超出限制。', 413)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                im = Image.open(io.BytesIO(raw))
                if im.format not in ('PNG', 'JPEG', 'WEBP') or getattr(im, 'n_frames', 1) > 1:
                    return error('UNSUPPORTED_IMAGE', '仅支持静态 JPG、PNG 或 WebP 图片。', 415)
                if im.width * im.height > app.config['MAX_IMAGE_PIXELS']:
                    return error('IMAGE_TOO_LARGE', '图片像素过高，请缩小后重试。', 413)
                im.load()
                im = ImageOps.exif_transpose(im).convert('RGB')
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            return error('INVALID_IMAGE', '无法读取这张图片，请检查文件是否完整。', 415)
        if not jobs.slots.acquire(blocking=False):
            return error('QUEUE_FULL', '当前任务较多，请稍后再试。', 429)
        task_id, aid = str(uuid4()), str(uuid4())
        folder = data / 'tasks' / task_id
        try:
            folder.mkdir(parents=True)
            # Lossless, orientation-normalized RGB copy; preserves model preprocessing and strips metadata.
            input_path = folder / 'input.png'
            im.save(input_path, 'PNG')
            created = now()
            expires = (datetime.now(timezone.utc) + timedelta(days=app.config['RETENTION_DAYS'])).isoformat()
            with db.connect() as conn:
                conn.execute('INSERT INTO detection_tasks (id,owner_id,filename,status,image_width,image_height,image_sha256,input_path,created_at,expires_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                             (task_id, owner(), file.filename.replace('\\', '/').split('/')[-1][:180], 'queued', im.width, im.height,
                              hashlib.sha256(raw).hexdigest(), str(input_path.relative_to(data)), created, expires))
                conn.execute('INSERT INTO artifacts VALUES (?,?,?,?,?,?,?)',
                             (aid, task_id, 'original', None, str(input_path.relative_to(data)), 'image/png', created))
        except Exception:
            jobs.slots.release()
            if folder.exists():
                shutil.rmtree(folder)
            raise
        jobs.submit_reserved(task_id)
        return jsonify(task_id=task_id, status='queued', poll_url=f'/api/v1/tasks/{task_id}'), 202

    def page_args():
        try:
            return min(50, max(1, int(request.args.get('limit', 20)))), max(0, int(request.args.get('offset', 0)))
        except ValueError:
            return 20, 0

    @app.get('/api/v1/tasks')
    def task_list():
        limit, offset = page_args()
        rows = db.all('SELECT * FROM detection_tasks WHERE owner_id=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?', (owner(), limit + 1, offset))
        return jsonify(items=[task_public(row) for row in rows[:limit]], next_offset=offset + limit if len(rows) > limit else None)

    @app.get('/api/v1/tasks/<task_id>')
    def task_get(task_id):
        row = owned_task(task_id)
        if not row:
            return error('NOT_FOUND', '未找到这次鉴别。', 404)
        result = task_public(row)
        original = db.one("SELECT id FROM artifacts WHERE task_id=? AND kind='original'", (task_id,))
        result['original_url'] = f"/api/v1/artifacts/{original['id']}" if original else None
        return jsonify(result)

    @app.delete('/api/v1/tasks/<task_id>')
    def task_delete(task_id):
        row = owned_task(task_id)
        if not row:
            return error('NOT_FOUND', '未找到这次鉴别。', 404)
        if row['status'] in ('queued', 'running'):
            return error('TASK_BUSY', '请等待任务结束后再删除。', 409)
        # The ID came from a stored UUID row; still enforce the storage boundary.
        folder = (data / 'tasks' / row['id']).resolve()
        if folder.is_relative_to((data / 'tasks').resolve()) and folder.exists():
            shutil.rmtree(folder)
        db.execute('DELETE FROM detection_tasks WHERE id=? AND owner_id=?', (task_id, owner()))
        return '', 204

    @app.get('/api/v1/artifacts/<aid>')
    def artifact_get(aid):
        row = db.one('SELECT a.* FROM artifacts a JOIN detection_tasks t ON a.task_id=t.id WHERE a.id=? AND t.owner_id=?', (aid, owner()))
        if not row:
            return error('NOT_FOUND', '图片不存在或已过期。', 404)
        path = (data / row['relative_path']).resolve()
        if not path.is_relative_to(data) or not path.is_file():
            return error('NOT_FOUND', '图片不存在或已过期。', 404)
        return send_file(path, mimetype=row['mime_type'], max_age=0)

    @app.route('/api/v1/conversations', methods=['GET', 'POST'])
    def conversations():
        if request.method == 'POST':
            cid, timestamp = str(uuid4()), now()
            db.execute('INSERT INTO conversations VALUES (?,?,?,?,?)', (cid, owner(), '新的对话', timestamp, timestamp))
            return jsonify(id=cid, title='新的对话'), 201
        limit, offset = page_args()
        rows = db.all('SELECT id,title,created_at,updated_at FROM conversations WHERE owner_id=? ORDER BY updated_at DESC,id DESC LIMIT ? OFFSET ?', (owner(), limit + 1, offset))
        return jsonify(items=rows[:limit], next_offset=offset + limit if len(rows) > limit else None)

    @app.route('/api/v1/conversations/<cid>', methods=['GET', 'DELETE'])
    def conversation_detail(cid):
        row = owned_conversation(cid)
        if not row:
            return error('NOT_FOUND', '对话不存在。', 404)
        if request.method == 'DELETE':
            if db.one("SELECT id FROM messages WHERE conversation_id=? AND status IN ('pending','running')", (cid,)):
                return error('CONVERSATION_BUSY', '请等待回复结束后再删除。', 409)
            db.execute('DELETE FROM conversations WHERE id=? AND owner_id=?', (cid, owner()))
            return '', 204
        messages = db.all('SELECT id,role,content,status,model,error_code,created_at,sequence FROM messages WHERE conversation_id=? ORDER BY sequence', (cid,))
        return jsonify(id=cid, title=row['title'], messages=messages)

    @app.post('/api/v1/conversations/<cid>/messages')
    def message_post(cid):
        if not owned_conversation(cid):
            return error('NOT_FOUND', '对话不存在。', 404)
        content = (request.get_json(silent=True) or {}).get('content')
        if not isinstance(content, str) or not content.strip() or len(content) > 4000:
            return error('INVALID_MESSAGE', '请输入 1–4000 字的消息。')
        if not chat.slots.acquire(blocking=False):
            return error('CHAT_BUSY', '对话服务繁忙，请稍后再试。', 429)
        uid, mid = str(uuid4()), str(uuid4())
        try:
            with db.connect() as conn:
                conn.execute('BEGIN IMMEDIATE')
                if conn.execute("SELECT id FROM messages WHERE conversation_id=? AND status IN ('pending','running')", (cid,)).fetchone():
                    chat.slots.release()
                    return error('CONVERSATION_BUSY', '请等待上一条回复。', 409)
                count = conn.execute('SELECT COUNT(*) FROM messages WHERE conversation_id=?', (cid,)).fetchone()[0]
                if count >= 400:
                    chat.slots.release()
                    return error('CONVERSATION_FULL', '本段对话已满，请开启新的对话。', 409)
                conn.execute('INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?)', (uid, cid, 'user', content.strip(), 'completed', None, None, now(), count + 1))
                ready = chat.configured()
                conn.execute('INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?)', (mid, cid, 'assistant', '' if ready else '对话服务尚未连接。你的消息已保存，配置完成后可继续交流。',
                             'pending' if ready else 'failed', app.config['LLM_MODEL'] or None, None if ready else 'LLM_NOT_CONFIGURED', now(), count + 2))
                conn.execute('UPDATE conversations SET title=CASE WHEN title=? THEN ? ELSE title END,updated_at=? WHERE id=?', ('新的对话', content.strip()[:24], now(), cid))
        except Exception:
            chat.slots.release()
            raise
        if ready:
            chat.submit_reserved(cid, mid)
        else:
            chat.slots.release()
        return jsonify(message_id=mid, status='pending' if ready else 'failed'), 202

    @app.get('/')
    def index():
        return send_from_directory(ROOT / 'web' / 'dist', 'index.html')

    @app.get('/assets/<path:filename>')
    def assets(filename):
        return send_from_directory(ROOT / 'web' / 'dist' / 'assets', filename)

    return app


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    create_app().run(host=os.getenv('HOST', '127.0.0.1'), port=int(os.getenv('PORT', '6006')), debug=False, threaded=True)
