from cache import redis_conn
from rq import Worker, Queue

listen = ["default"]

if __name__ == "__main__":
    # Create queues with explicit Redis connection
    queues = [Queue(name, connection=redis_conn) for name in listen]

    # Create worker with explicit Redis connection
    worker = Worker(queues, connection=redis_conn)
    print("[Worker] Listening for jobs...")
    worker.work()

