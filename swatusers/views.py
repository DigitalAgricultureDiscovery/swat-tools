from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render, resolve_url
from django.template.response import TemplateResponse
from swatusers.forms import ContactUsForm, InternetSpeedForm, LoginForm, RegistrationForm
from swatusers.models import UserTask, SwatUser
from swatapps.settings.production import ADMINS, NORECAPTCHA_SITE_KEY, \
    NORECAPTCHA_SECRET_KEY

from datetime import datetime, timedelta
import json
import os
import shutil
import urllib

from .mytools import mydatabase


def index(request):
    context = {'title': ('SWAT Tools Home')}
    return TemplateResponse(
        request,
        'swatusers/index.html',
        context)


def authenticate_user(request):
    """ Validates user signing in """

    # Reset session values
    request.session['dberror'] = []
    request.session['error'] = []
    request.session['progress_message'] = []
    if not request.user.is_authenticated():
        next = ""
        if request.GET:
            next = request.GET['next']
        if request.method == 'POST':
            # Authenticate request
            form = LoginForm(data=request.POST)
            if form.is_valid():
                email = request.POST['email']
                password = request.POST['password']
                user = authenticate(email=email, password=password)

                # If successfully authenticated, login user and redirect
                if user is not None:
                    if user.is_active:
                        request.session['name'] = user.email
                        login(request, user)
                        if user.upload_speed == 0:
                            return HttpResponseRedirect(
                            resolve_url('speed'))
                        elif next == "":
                            return HttpResponseRedirect(
                                resolve_url('tool_selection'))
                        else:
                            return HttpResponseRedirect(next)
                    else:
                        request.session['dberror'] = 'Account not activated.'

                        return render(
                            request,
                            'registration/login.html',
                            {'form': LoginForm})
                else:
                    request.session[
                        'dberror'] = 'Sorry, could not find match ' + \
                                     'for submitted credentials.'
                    return render(
                        request,
                        'registration/login.html',
                        {'form': LoginForm})
            else:
                request.session[
                    'dberror'] = 'Unable to login. Make sure you are ' \
                                 'entering a valid email address.'
                return render(
                    request,
                    'registration/login.html',
                    {'form': LoginForm})
        else:
            return render(
                request,
                'registration/login.html',
                {'form': LoginForm, 'next': next}
            )
    else:
        return HttpResponseRedirect(resolve_url('tool_selection'))


@login_required
def set_upload_speed(request):

    if request.method == 'POST':

        form = InternetSpeedForm(request, request.POST or None)

        if form.is_valid():
            request.user.upload_speed = form.cleaned_data["upload_speed"]
            request.user.save()
            return render(
                request,
                "swatusers/upload_speed.html", {
                    "form": InternetSpeedForm(request),
                    "status": "success"
                },
                content_type="text/html")
        else:
            return render(
                request, "swatusers/upload_speed.html", {
                    "form": form
                },
                content_type="text/html")
    else:
        form = InternetSpeedForm(request)

    return render(
        request,
        "swatusers/upload_speed.html", {
            "form": form})


def infographic(request):
    # Return the infographic template

    return render(
        request,
        'swatusers/infographic.html',
    )


def validate_recaptcha_response(recaptcha_response):
    """ Verifies the g-recaptcha-response payload with Google. """

    # Google's verification url
    verification_url = "https://www.google.com/recaptcha/api/siteverify"

    # Parameters required for verification
    verification_data = {
        "secret": NORECAPTCHA_SECRET_KEY,
        "response": recaptcha_response
    }

    # Post verification data to verification url
    response = urllib.request.urlopen(
        verification_url,
        urllib.parse.urlencode(verification_data).encode("utf-8"))

    # Read response from verification post
    content = json.loads(response.read().decode("utf-8"))

    return content["success"]


def register_user(request):
    """ This view takes all information Registration html page and
        save into the database """
    request.session['dberror'] = []

    # Only allow users not signed in to view the registration page
    if request.user.is_authenticated():
        return HttpResponseRedirect(resolve_url('tool_selection'))
    else:
        if request.method == 'POST':

            form = RegistrationForm(data=request.POST)

            # Capture the Google recaptcha response
            recaptcha_response = request.POST.get("g-recaptcha-response")

            # Pass response to verification method
            recaptcha_is_valid = validate_recaptcha_response(recaptcha_response)

            # Check if forms validate
            if form.is_valid() and recaptcha_is_valid:
                # Save new user and create/save profile
                new_user = form.save()

                # Render login page so new user can sign in
                return HttpResponseRedirect(resolve_url('register_complete'))
            else:
                return render(
                    request,
                    'registration/register.html',
                    {
                        'form': form,
                        'sitekey': NORECAPTCHA_SITE_KEY,
                        'recaptcha_failed': True
                    }
                )
        else:
            form = RegistrationForm()
        return render(
            request,
            "registration/register.html",
            {
                'form': form,
                'sitekey': NORECAPTCHA_SITE_KEY
            }
        )


@login_required
def contact_us(request):
    """ Renders Contact Us page which enables user to email administrator """

    # only allow users not signed in to view the registration page
    if request.user.is_authenticated():
        if request.method == 'POST':
            # send email
            contact_form = ContactUsForm(request.POST)
            if contact_form.is_valid():
                try:
                    send_mail_status = send_mail(
                        subject=contact_form.cleaned_data['subject'],
                        message='',
                        from_email='SWAT Tools',
                        recipient_list=[i[1] for i in ADMINS],
                        fail_silently=False,
                        html_message=contact_form.cleaned_data[
                                         'message'] + '<br><br>Sent by ' + request.user.get_full_name() + ' (<a href="mailto:' + request.user.email + '">' + request.user.email + '</a>).'
                    )
                    if send_mail_status != 0:
                        return HttpResponseRedirect(
                            resolve_url('contact_us_done'))
                    else:
                        return HttpResponseRedirect(
                            resolve_url('contact_us_error'))
                except:
                    return HttpResponseRedirect(
                        resolve_url('contact_us_error'))
            else:
                return HttpResponseRedirect(resolve_url('contact_us_error'))
        else:
            return render(
                request,
                'swatusers/contact_us.html',
                {'form': ContactUsForm})
    else:
        return render(request, 'registration/login.html')


def delete_user_data_and_logout(request):
    """ Removes user data and logs them out """

    # Delete user data and flush current session
    delete_user_data(request)
    request.session.flush()
    # Sign user out and return to login page
    logout(request)

    return HttpResponseRedirect(resolve_url('login'))


def delete_user_data(request):
    """ This view delete's the signed in user's data. """

    dir = settings.PROJECT_DIR + '/user_data/' + request.user.email + '/swatluu'

    if (dir is not None):
        # Delete user's uploaded input data
        if os.path.exists(dir + '/input'):
            shutil.rmtree(dir + '/input')
        # Delete user's output data
        if os.path.exists(dir + '/output'):
            shutil.rmtree(dir + '/output')

            # Delete any processes this user might have in the database
            # CurrentProcesses.objects.filter(user_id=request.user.id).delete()


def generate_user_activity_report(request):
    """ Creates and emails a summary of user activity to ADMINS. """

    # Default response
    response = {"success": False}

    # If hidden api token available in header
    if "HTTP_APITOKEN" in request.META:
        apikey = request.META["HTTP_APITOKEN"]

        if apikey == settings.APIKEY:
            # Will hold results
            all_results = {
                "week": {},
                "month": {},
                "year": {}
            }

            # Establish connection to the database
            db = mydatabase.MyDatabase(
                mycnf=settings.PROJECT_DIR + "/swatapps/my.cnf")

            # Connect to database
            db.connect_to_database()

            # Get start and end for query (today plus 1 day minus 7 days)
            # Get start and end date for query (today plus 1 day minus 7 days)
            todays_date = datetime.today()
            start_date = datetime.today() - timedelta(days=7)
            end_date = datetime.today() + timedelta(days=1)

            todays_date_formatted = "%s-%s-%s" % (
                str(todays_date.year), str(todays_date.month).zfill(2),
                str(todays_date.day).zfill(2))
            start_date_formatted = "%s-%s-%s" % (
                str(start_date.year), str(start_date.month).zfill(2),
                str(start_date.day).zfill(2))
            end_date_formatted = "%s-%s-%s" % (
                str(end_date.year), str(end_date.month).zfill(2),
                str(end_date.day).zfill(2))

            # Create query of database for new users in last 7 days
            query = "SELECT id FROM `swatusers_swatuser` "
            query += "WHERE date_joined BETWEEN "
            query += "'%s' AND '%s';" % (
            start_date_formatted, end_date_formatted)

            # Make query on database
            query_results = db.query_database(query)

            # Fetch records for query to get total of new users this week
            new_users_this_week = len(db.fetch_records(query_results, "all"))
            all_results["week"]["new_users"] = new_users_this_week

            # Get date for start of current month
            month_date = "%s-%s-01" % (
            str(todays_date.year), str(start_date.month).zfill(2))

            # Create query of data for new users this month
            query = "SELECT id FROM `swatusers_swatuser` "
            query += "WHERE date_joined BETWEEN "
            query += "'%s' AND '%s';" % (month_date, todays_date_formatted)

            # Make query on database
            query_results = db.query_database(query)

            # Fetch records for query to get total of new users this month
            new_users_this_month = len(db.fetch_records(query_results, "all"))
            all_results["month"]["new_users"] = new_users_this_month

            # Get date for start of year
            year_date = "%s-01-01" % (str(todays_date.year))

            # Create query of data for new users this year
            query = "SELECT id FROM `swatusers_swatuser` "
            query += "WHERE date_joined BETWEEN "
            query += "'%s' AND '%s';" % (year_date, todays_date_formatted)

            # Make query on database
            query_results = db.query_database(query)

            # Fetch records for query to get total of new users this year
            new_users_this_year = len(db.fetch_records(query_results, "all"))
            all_results["year"]["new_users"] = new_users_this_year

            # Email summary
            email_summary_msg = "-" * 47
            email_summary_msg += "<br />"
            email_summary_msg += "<strong>SWAT Tools new user summary</strong>"
            email_summary_msg += "<br />"
            email_summary_msg += "-" * 47
            email_summary_msg += "<br />Last Week (%s - %s):&nbsp;%s" % (
                start_date_formatted, todays_date_formatted,
                str(all_results["week"]["new_users"]))
            email_summary_msg += "<br />Current Month (%s-%s): %s" % (
                str(todays_date.year), str(todays_date.month).zfill(2),
                str(all_results["month"]["new_users"]))
            email_summary_msg += "<br />Current Year (%s): %s" % (
            str(todays_date.year), str(all_results["year"]["new_users"]))
            email_summary_msg += "<br />"
            email_summary_msg += "-" * 47

            # Send mail
            send_mail_status = send_mail(
                subject="SWAT Tools User Activity Summary",
                message="",
                from_email="SWAT Tools",
                recipient_list=[i[1] for i in ADMINS],
                fail_silently=True,
                html_message=email_summary_msg
            )
            if send_mail_status != 0:
                response = {"success": True}

    return JsonResponse(response)


def contact_us_done(request):
    """ Renders page indicating the email has been sent successfully """

    context = {'title': ('Contact email successfully sent')}

    return TemplateResponse(request, 'swatusers/contact_us_done.html', context)


def contact_us_error(request):
    """ Renders page indicating there was an error while sending
        the contact email """

    context = {'title': ('Contact email failed to send')}

    return TemplateResponse(
        request,
        'swatusers/contact_us_error.html',
        context)


def register_complete(request):
    """ Renders page informing the user their registration was a success. """

    context = {'title': ('Registration completed')}

    return TemplateResponse(request, 'swatusers/register_complete.html',
                            context)


@login_required
def tool_selection(request):

    context = {'title': ('SWAT Tools Selection')}

    return TemplateResponse(
        request,
        'swatusers/tool_selection.html',
        context)


def get_expiration_date(start_datetime):
    """
    Uses Python's datetime to calculate expiration date for processed data.

    Parameters
    ----------
    start_datetime: datetime
        Date and time (mm-dd-YYYY HH:MM:SS) the process
        expiration countdown starts.

    Returns
    -------
    date_string: string
        Date and time (mm-dd-YYYY HH:MM:SS) 48 hours from the
        start_datetime in string format.
    """

    return (start_datetime + timedelta(hours=48)).strftime(
        "%m-%d-%Y %H:%M:%S %Z")


@login_required
def task_status(request):

    # Query user tasks
    user_tasks_query = UserTask.objects.filter(email=request.user.email)

    if user_tasks_query:
        user_tasks = []
        for task in user_tasks_query:
            # Get name of tool
            task_name = task.task_id.split('_')[2]
            # Change to proper name
            if task_name == 'luuchecker':
                task_name = 'LUU Checker'
            elif task_name == 'swatluu':
                task_name = 'SWAT LUU'
            elif task_name == 'uncertainty':
                task_name = 'LUU Uncertainty'
            elif task_name == 'fieldswat':
                task_name = 'Field SWAT'
            else:
                task_name = 'Unknown'

            # Download URL
            task_download_url = False

            # Set appropriate task status message
            if int(task.task_status) == 0:
                task_status = 'processing'
            elif int(task.task_status) == 1:
                task_status = 'done'
                if task_name == 'LUU Checker':
                    task_download_url = 'https://saraswat-swat.rcac.purdue.edu/luuchecker/download_data?id=' + task.task_id
                elif task_name == 'SWAT LUU':
                    task_download_url = 'https://saraswat-swat.rcac.purdue.edu/swatluu/download_data?id=' + task.task_id
                elif task_name == 'LUU Uncertainty':
                    task_download_url = 'https://saraswat-swat.rcac.purdue.edu/uncertainty/download_data?id=' + task.task_id
                elif task_name == 'Field SWAT':
                    task_download_url = 'https://saraswat-swat.rcac.purdue.edu/fieldswat/download_data?id=' + task.task_id
            else:
                task_status = 'error'

            user_tasks.append({
                'name': task_name,
                'stime': task.time_started.strftime("%m-%d-%Y %H:%M:%S %Z"),
                'etime': task.time_completed.strftime("%m-%d-%Y %H:%M:%S %Z"),
                'status': task_status,
                'download': task_download_url,
                'expiration': get_expiration_date(task.time_completed)
            })

        # Test data
        context = {'task_items': user_tasks}

        return render(request, 'swatusers/task_status.html', context)
    else:
        return render(request, 'swatusers/task_status.html')
