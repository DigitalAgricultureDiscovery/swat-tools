from django import forms


class UploadDestinationForm(forms.Form):

    file_size = forms.IntegerField()
