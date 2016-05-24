"""
WSGI config for swatapps project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/howto/deployment/wsgi/
"""

from django.conf import settings
import os
import sys

sys.path.append(settings.BASE_DIR + '')

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "swatapps.settings")

application = get_wsgi_application()
