"""
WSGI config for swatapps project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

SETTING_ENV = os.environ['SWATAPPS_SETTING_ENV']

os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"swatapps.settings.{SWATAPPS_SETTING_ENV}")

application = get_wsgi_application()
