import os
from logging.config import dictConfig
from pathlib import Path

from .logging_config import get_logging_config


# Admins (name, email)

ADMINS = [admin.split(',') for admin in os.environ['ADMINS'].split(';')]


# Build paths inside the project like this: BASE_DIR / 'subdir'.

BASE_DIR = str(Path(__file__).resolve().parent)
PROJECT_DIR = str(Path(__file__).parents[1])

print(BAE)