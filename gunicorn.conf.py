# Gunicorn configuration
# The report generation pipeline (Tableau export + AI insights + PPTX build)
# takes 60-120 seconds. The default 30s timeout kills workers mid-job,
# causing the browser to spin indefinitely. 300s gives plenty of headroom.

timeout = 300          # worker timeout in seconds (default is 30 — too short)
workers = 1            # single worker avoids session/cache conflicts
threads = 4            # handle concurrent requests within the worker
bind = "0.0.0.0:5002"
loglevel = "info"
