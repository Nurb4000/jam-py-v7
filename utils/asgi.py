#asgi.py
# Used for GH  Actions on Windows pyinstaller 
from jam.wsgi import create_application
from asgiref.wsgi import WsgiToAsgi
application = WsgiToAsgi(create_application(__file__))
