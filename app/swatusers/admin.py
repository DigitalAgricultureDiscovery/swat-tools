from django.contrib import admin

# Register your models here.
from .models import UserTask

admin.site.register(UserTask)
