from django.shortcuts import render


def page_not_found(request):
    return render(request, "errors/page_not_found.html")


def error(request):
    return render(request, "errors/error.html")


def permission_denied(request):
    return render(request, "errors/permission_denied.html")


def bad_request(request):
    return render(request, "errors/bad_request.html")
