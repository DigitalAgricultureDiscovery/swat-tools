from swatusers.models import SwatUser


class EmailAuthBackend(object):
    """ 
    A custom authentication backend. Allows users to 
    log in using their email address. 
    """

    def authenticate(self, email=None, password=None):
        """ Authentication method """

        try:
            user = SwatUser.objects.get(email=email)
            if user.check_password(password):
                return user
        except SwatUser.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            user = SwatUser.objects.get(pk=user_id)
            if user.is_active:
                return user
            return None
        except SwatUser.DoesNotExist:
            return None
