from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models


class SwatUserManager(BaseUserManager):
    def create_user(self, email, first_name, last_name, country, state, is_active, is_superuser, is_staff, date_joined, password=None):
        user = self.model(
            email=email,
            first_name=first_name,
            last_name=last_name,
            country=country,
            state=state,
            is_active=is_active,
            is_superuser=is_superuser,
            is_staff=is_staff,
            date_joined=date_joined)

        return user

    def create_superuser(self, email, first_name, last_name, country, state, is_active, is_superuser, is_staff, date_joined, password):
        user = self.create_user(
            email, first_name, last_name, country, state, is_active, is_superuser, is_staff, date_joined, password=password)

        user.save()
        return user


class SwatUser(AbstractBaseUser):
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    organization = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=30)
    state = models.CharField(max_length=30)
    is_active = models.BooleanField(default=True)
    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    
    def __unicode__(self):
        return self.email

    def get_full_name(self):
        """
        Returns the first_name plus the last_name, with a space in between.
        """
        full_name = '%s %s' % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self):
        "Returns the short name for the user."
        return self.first_name

    def email_user(self, subject, message, from_email=None, **kwargs):
        """
        Sends an email to this User.
        """
        send_mail(subject, message, from_email, [self.email], **kwargs)

    objects = SwatUserManager()


class UserTask(models.Model):
    """ Information on requested task by the users. """
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    email = models.EmailField()
    task_id = models.CharField(max_length=100)
    task_status = models.BooleanField()
    time_started = models.DateTimeField(auto_now_add=True)
    time_completed = models.DateTimeField()
