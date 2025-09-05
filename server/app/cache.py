import os
import redis

REDIS_URL = os.getenv("REDIS_URL")
redis_conn = redis.from_url(REDIS_URL)

def close_redis():
    try:
        redis_conn.save()  # optional: force Redis to persist data if configured
        redis_conn.close()
    except Exception:
        pass
