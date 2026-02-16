# Procfile for deployment on Render/Railway
# Use Gunicorn with Eventlet for WebSocket support

web: gunicorn -k gevent -w 1 --bind 0.0.0.0:$PORT app:app
