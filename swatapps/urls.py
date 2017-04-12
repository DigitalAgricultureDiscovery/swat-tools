"""swatapps URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""

from django.conf.urls import include, url
from django.contrib.auth import views as auth_views

from luuchecker import views as luuchecker_views
from swatusers import views as swatusers_views
from swatluu import views as swatluu_views
from uncertainty import views as uncertainty_views
from fieldswat import views as fieldswat_views


urlpatterns = [
    url(r'^$', swatusers_views.index, name='index'),

    # presign s3 upload
    url(r'^sign_s3/$', swatluu_views.sign_s3, name='sign_s3'),

    # Registration view from swatusers views
    url(r'^register$', swatusers_views.register_user, name='register'),
    url(r'^register_complete$', swatusers_views.register_complete, name='register_complete'),

    # Contact Us form urls
    url(r'^contact_us$', swatusers_views.contact_us, name='contact_us'),
    url(r'^contact_us_done$', swatusers_views.contact_us_done, name='contact_us_done'),
    url(r'^contact_us_error$', swatusers_views.contact_us_error, name='contact_us_error'),

    # Login with custom login and logout view
    url(r'^login$', swatusers_views.authenticate_user, name='login'),
    url(r'^logout$', auth_views.logout, name='logout'),

    # Change password views from django authentication system
    url(r'^password_change/$', auth_views.password_change, name='password_change'),
    url(r'^password_change/done/$', auth_views.password_change_done, name='password_change_done'),

    # Password reset views from django authentication system
    url(r'^password_reset$', auth_views.password_reset, name='password_reset'),
    url(r'^password_reset_done$', auth_views.password_reset_done, name='password_reset_done'),
    url(r'^password_reset_confirm/(?P<uidb64>[0-9A-Za-z]+)-(?P<token>.+)/$', auth_views.password_reset_confirm, name='password_reset_confirm'),
    url(r'^password_reset_complete$', auth_views.password_reset_complete, name='password_reset_complete'),

    # Select tool
    url(r'^tool_selection$', swatusers_views.tool_selection, name='tool_selection'),

    # Task status
    url(r'^task_status$', swatusers_views.task_status, name='task_status'),

    # User summary
    url(r'^user_activity_report$', swatusers_views.generate_user_activity_report, name='user_activity_report'),

    # SWAT LUU urls
    url(r'^swatluu$', swatluu_views.index, name='swatluu'),
    url(r'^swatluu/upload_swat_model_zip$', swatluu_views.upload_swat_model_zip, name='swatluu/upload_swat_model_zip'),
    url(r'^swatluu/upload_landuse_zip$', swatluu_views.upload_landuse_zip, name='swatluu/upload_landuse_zip'),
    url(r'^swatluu/select_number_of_landuse_layers$', swatluu_views.select_number_of_landuse_layers, name='swatluu/select_number_of_landuse_layers'),
    url(r'^swatluu/validate_selected_landuse_layers$', swatluu_views.validate_selected_landuse_layers, name='swatluu/validate_selected_landuse_layers'),
    url(r'^swatluu/upload_lookup_file$', swatluu_views.upload_lookup_file, name='swatluu/upload_lookup_file'),
    url(r'^swatluu/reset$', swatluu_views.reset, name='swatluu/reset'),
    url(r'^swatluu/process$', swatluu_views.runit, name='swatluu/process'),
    url(r'^swatluu/download_data$', swatluu_views.download_data, name='swatluu/download_data'),

    # LUU Checker urls
    url(r'^luuchecker$', luuchecker_views.index, name='luuchecker'),
    url(r'^luuchecker/upload_subbasin_shapefile_zip$', luuchecker_views.upload_subbasin_shapefile_zip, name='luuchecker/upload_subbasin_shapefile_zip'),
    url(r'^luuchecker/upload_landuse_folder_zip$', luuchecker_views.upload_landuse_folder_zip, name='luuchecker/upload_landuse_folder_zip'),
    url(r'^luuchecker/upload_base_landuse_raster_file$', luuchecker_views.upload_base_landuse_raster_file, name='luuchecker/upload_base_landuse_raster_file'),
    url(r'^luuchecker/select_number_of_landuse_layers$', luuchecker_views.select_number_of_landuse_layers, name='luuchecker/select_number_of_landuse_layers'),
    url(r'^luuchecker/upload_selected_landuse_layers$', luuchecker_views.upload_selected_landuse_layers, name='luuchecker/upload_selected_landuse_layers'),
    url(r'^luuchecker/select_percentage$', luuchecker_views.select_percentage, name='luuchecker/select_percentage'),
    url(r'^luuchecker/reset$', luuchecker_views.reset, name='luuchecker/reset'),
    url(r'^luuchecker/process$', luuchecker_views.request_process, name='luuchecker/process'),
    url(r'^luuchecker/download_data$', luuchecker_views.download_data, name='luuchecker/download_data'),

    # LUU Uncertainty urls
    url(r'^uncertainty$', uncertainty_views.index, name='uncertainty'),
    url(r'^uncertainty/upload_swat_model_zip$', uncertainty_views.upload_swat_model_zip, name='uncertainty/upload_swat_model_zip'),
    url(r'^uncertainty/upload_landuse_zip$', uncertainty_views.upload_landuse_zip, name='uncertainty/upload_landuse_zip'),
    url(r'^uncertainty/upload_landuse_layer$', uncertainty_views.upload_landuse_layer, name='uncertainty/upload_landuse_layer'),
    url(r'^uncertainty/upload_lookup_file$', uncertainty_views.upload_lookup_file, name='uncertainty/upload_lookup_file'),
    #url(r'^uncertainty/upload_swatexe_file$', uncertainty_views.upload_swatexe_file, name='uncertainty/upload_swatexe_file'),
    url(r'^uncertainty/reset$', uncertainty_views.reset, name='uncertainty/reset'),
    url(r'^uncertainty/process$', uncertainty_views.request_process, name='uncertainty/process'),
    url(r'^uncertainty/download_data$', uncertainty_views.download_data, name='uncertainty/download_data'),
    url(r'^uncertainty/update_error_percentage$', uncertainty_views.update_error_percentage, name='uncertainty/update_error_percentage'),

    # Field SWAT
    url(r'^fieldswat$', fieldswat_views.index, name='fieldswat'),
    url(r'^fieldswat/upload_swat_model_zip$', fieldswat_views.upload_swat_model_zip, name='fieldswat/upload_swat_model_zip'),
    url(r'^fieldswat/select_year$', fieldswat_views.select_year, name='fieldswat/select_year'),
    url(r'^fieldswat/upload_fields_shapefile_zip$', fieldswat_views.upload_fields_shapefile_zip, name='fieldswat/upload_fields_shapefile_zip'),
    url(r'^fieldswat/confirm_output_and_agg$', fieldswat_views.confirm_output_and_agg, name='fieldswat/confirm_output_and_agg'),
    url(r'^fieldswat/process$', fieldswat_views.request_process, name='fieldswat/process'),
    url(r'^fieldswat/reset$', fieldswat_views.reset, name='fieldswat/reset'),
    url(r'^fieldswat/download_data$', fieldswat_views.download_data, name='fieldswat/download_data'),
]

