from django import forms
from swatusers.models import SwatUser
from django.conf import settings
import pickle


class RegistrationForm(forms.ModelForm):
    """ Extend UserCreationForm to include email, first name, and last name """

    email = forms.EmailField(widget=forms.widgets.TextInput, label='Email')
    password1 = forms.CharField(widget=forms.PasswordInput(), label='Password')
    password2 = forms.CharField(widget=forms.PasswordInput(), label='Password (again)')
    first_name = forms.CharField(widget=forms.widgets.TextInput, label="First name")
    last_name = forms.CharField(widget=forms.widgets.TextInput, label="Last name")
    organization = forms.CharField(widget=forms.widgets.TextInput, label='Organization (optional)', required=False)
    country = forms.ChoiceField(
        choices=pickle.load(open(str(settings.PROJECT_DIR) + '/swatusers/countries.p', 'rb')),
        label='Country',
        initial='United States of America'
    )
    state = forms.CharField(widget=forms.widgets.TextInput, label='State')

    class Meta:
        model = SwatUser
        fields = ('email', 'password1', 'password2', 'first_name',
                  'last_name', 'organization', 'country', 'state')

    def clean(self):
        """ Cleans data and validates. """
        cleaned_data = super(RegistrationForm, self).clean()

        # Check if password and re-typed password match
        if 'password1' in cleaned_data and 'password2' in cleaned_data:
            if cleaned_data['password1'] != cleaned_data['password2']:
                raise forms.ValidationError("Passwords don't match. Please "
                                            "enter both fields again.")

        # Check if email available
        if 'email' in cleaned_data:
            query_email = SwatUser.objects.filter(email=cleaned_data["email"])

            if query_email:
                raise forms.ValidationError("Sorry, this email address is "
                                            "already in use.")

        return cleaned_data

    def save(self, commit=True):
        user = super(RegistrationForm, self).save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class ContactUsForm(forms.Form):
    """ Form for the Contact Us page """

    # Create subject and message fields
    subject = forms.CharField(label='Subject')
    message = forms.CharField(widget=forms.Textarea, label='Message')


class LoginForm(forms.Form):
    """Form for the user to login"""

    email = forms.EmailField(widget=forms.widgets.TextInput, label='Email')
    password = forms.CharField(widget=forms.PasswordInput(), label='Password')

    class Meta:
        fields = ['email', 'password']


class InternetSpeedForm(forms.Form):
    """ Form for the user to set their internet speed. """

    def __init__(self, request, *args, **kwargs):
        super(InternetSpeedForm, self).__init__(*args, **kwargs)
        current_upload_speed = request.user.upload_speed

        if (int(current_upload_speed) > 0):
            # Remove "Not Provided" option if user has
            # already selected a speed range
            UPLOAD_SPEED_CHOICES = (
                (1, '<= 256 Kbps'),
                (2, '> 256 Kbps <= 1 Mbps'),
                (3, '> 1 Mbps <= 10 Mbps'),
                (4, '> 10 Mbps <= 25 Mbps'),
                (5, '> 25 Mbps')
            )
        else:
            UPLOAD_SPEED_CHOICES = (
                (0, 'Not Provided'),
                (1, '<= 256 Kbps'),
                (2, '> 256 Kbps <= 1 Mbps'),
                (3, '> 1 Mbps <= 10 Mbps'),
                (4, '> 10 Mbps <= 25 Mbps'),
                (5, '> 25 Mbps')
            )

        self.fields["upload_speed"] = forms.ChoiceField(
            label="Upload Speed (Optional)",
            widget=forms.RadioSelect,
            choices=UPLOAD_SPEED_CHOICES,
            initial=current_upload_speed
        )
