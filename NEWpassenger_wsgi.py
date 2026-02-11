import sys
import os

# Add your project directory to the sys.path
project_home = '/home/USERNAME/public_html/keyhunt-server'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Activate virtual environment (if using venv)
activate_this = os.path.join(project_home, 'venv', 'bin', 'activate_this.py')
if os.path.exists(activate_this):
    with open(activate_this) as f:
        exec(f.read(), {'__file__': activate_this})

# Import uvicorn for FastAPI
from fastapi import FastAPI
from app import app  # import your FastAPI app from app.py

# Passenger requires WSGI application
# Wrap FastAPI in WSGI using asgi2wsgi
from asgiref.wsgi import WsgiToAsgi
from wsgiref.simple_server import make_server

application = app  # Passenger will call `application`



