import multiprocessing

bind = "0.0.0.0"
workers = (multiprocessing.cpu_count() * 2) + 1
worker_class = "gevent"
timeout = 230
max_requests = 1000
max_requests_jitter = 50
log_file = "-"