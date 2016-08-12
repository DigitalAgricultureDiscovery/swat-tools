from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, QueryDict
from django.shortcuts import render, resolve_url
from django.template.response import TemplateResponse
from django.template import RequestContext
from forms import ContactUsForm, LoginForm, RegistrationForm
from models import UserTask
from swatapps.settings import ADMINS

import datetime
import os
import shutil


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

                # If successfully authenticated, login user and redirect to index
                if user is not None:
                    if user.is_active:
                        request.session['name'] = user.email
                        login(request, user)
                        if next == "":
                            return HttpResponseRedirect(resolve_url('tool_selection'))
                        else:
                            return HttpResponseRedirect(next)
                    else:
                        request.session['dberror'] = 'Account not activated.'

                        return render(
                            request,
                            'registration/login.html',
                            {'form': LoginForm})
                else:
                    request.session['dberror'] = 'Sorry, could not find match ' + \
                                                 'for submitted credentials.'
                    return render(
                        request,
                        'registration/login.html',
                        {'form': LoginForm})
            else:
                request.session['dberror'] = 'Unable to login, make sure you are entering your full email address.'
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
            
            # Check if forms validate
            if form.is_valid():
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
                    }
                )
        else:
            form = RegistrationForm()
        return render(
            request,
            "registration/register.html",
            {
                'form': form,
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
                        html_message=contact_form.cleaned_data['message'] + '<br><br>Sent by ' + request.user.get_full_name() + ' (<a href="mailto:' + request.user.email + '">' + request.user.email + '</a>).'
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
    dir = settings.BASE_DIR + '/user_data/' + request.user.email + '/swatluu'

    if (dir is not None):
        # Delete user's uploaded input data
        if os.path.exists(dir + '/input'):
            shutil.rmtree(dir + '/input')
        # Delete user's output data
        if os.path.exists(dir + '/output'):
            shutil.rmtree(dir + '/output')

    # Delete any processes this user might have in the database
    #CurrentProcesses.objects.filter(user_id=request.user.id).delete()


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
    return TemplateResponse(request, 'swatusers/register_complete.html', context)


@login_required
def tool_selection(request):
    context = {'title': ('SWAT Tool Selection')}
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
    return (start_datetime + datetime.timedelta(hours=48)).strftime("%m-%d-%Y %H:%M:%S")


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
            print "task_status: task.task_status"
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
                'stime': task.time_started.strftime("%m-%d-%Y %H:%M:%S"),
                'etime': task.time_completed.strftime("%m-%d-%Y %H:%M:%S"),
                'status': task_status,
                'download': task_download_url,
                'expiration': get_expiration_date(task.time_completed)
                })

        # Test data
        context = RequestContext(request)
        context.push({'task_items': user_tasks})
    
        return render(request, 'swatusers/task_status.html', context)
    else:
        return render(request, 'swatusers/task_status.html')