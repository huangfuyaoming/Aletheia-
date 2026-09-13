from server.db import Database
from server.maintenance import cleanup_expired
from server.settings import settings

if __name__ == '__main__':
    config = settings()
    count = cleanup_expired(Database(config['DATABASE']), config['DATA_DIR'])
    print(f'Removed {count} expired finished tasks.')
