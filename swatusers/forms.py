from captcha.fields import ReCaptchaField
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
    organization = forms.CharField(widget=forms.widgets.TextInput, label='Organization')
    country = forms.ChoiceField(
        choices=pickle.load(open(settings.BASE_DIR + '/swatusers/countries.p', 'rb')),
        label='Country'
    )
    state = forms.CharField(widget=forms.widgets.TextInput, label='State')

    captcha = ReCaptchaField()

    class Meta:
        model = SwatUser
        fields = ('email', 'password1', 'password2', 'first_name', 'last_name', 'organization', 'country', 'state')

    def clean(self):
        """ Cleans data and verifies passwords match. """
        cleaned_data = super(RegistrationForm, self).clean()
        if 'password1' in self.cleaned_data and 'password2' in self.cleaned_data:
            if self.cleaned_data['password1'] != self.cleaned_data['password2']:
                raise forms.ValidationError("Passwords don't match. Please enter both fields again.")
        
        return self.cleaned_data

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
