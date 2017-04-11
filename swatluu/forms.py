from django import forms

from s3direct.widgets import S3DirectWidget


class SwatModelForm(forms.Form):
    swat_model = forms.URLField(
        label="SWAT Model Input",
        widget=S3DirectWidget(dest="user_data"))

