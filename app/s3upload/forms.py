from django import forms


class UploadDestinationForm(forms.Form):

    file_size = forms.IntegerField()


class UpdateUploadStatusForm(forms.Form):

    file_name = forms.CharField(max_length=256)
    file_size = forms.IntegerField()
    status = forms.IntegerField()
