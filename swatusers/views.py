from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, QueryDict
from django.shortcuts import render, resolve_url
from django.template.response import TemplateResponse
from django.template import RequestContext
from forms import ContactUsForm, LoginForm, RegistrationForm

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
                        contact_form.cleaned_data['subject'],
                        contact_form.cleaned_data['message'],
                        request.user.get_full_name(),
                        ['swat.luc.tool@gmail.com', 'ben.hancock@gmail.com'],
                        fail_silently=False)
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

@login_required
def task_status(request):
    # Test data
    context = RequestContext(request)
    context.push({
        'task_items': [
            {'id': 'id_test1', 'stime': 'stime_test1', 'status': 'status_test1', 'download': 'download_test1'},
            {'id': 'id_test2', 'stime': 'stime_test2', 'status': 'status_test2', 'download': 'download_test2'}
        ]
    })
    
    return render(request, 'swatusers/task_status.html', context)