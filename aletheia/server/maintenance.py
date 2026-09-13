"""Maintenance never creates the web app or loads/resets active job executors."""
import shutil
from pathlib import Path
from .jobs import now


def cleanup_expired(db, data):
    data = Path(data).resolve()
    rows = db.all("SELECT id FROM detection_tasks WHERE expires_at<? AND status IN ('completed','failed')", (now(),))
    for row in rows:
        folder = (data / 'tasks' / row['id']).resolve()
        if folder.is_relative_to((data / 'tasks').resolve()) and folder.exists():
            shutil.rmtree(folder)
        db.execute('DELETE FROM detection_tasks WHERE id=?', (row['id'],))
    return len(rows)
