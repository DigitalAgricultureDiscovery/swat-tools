import os


def gtag_processor(request):
    return {'gtag': os.environ.get('GTAG', '')}
