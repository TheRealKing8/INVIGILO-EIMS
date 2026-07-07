"""WSGI entry point for gunicorn / uwsgi in production."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "invigilo.settings.prod")

application = get_wsgi_application()
