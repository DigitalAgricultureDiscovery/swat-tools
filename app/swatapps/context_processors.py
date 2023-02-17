import os


def gtag_ga4_processor(request):
    return {'gtag_ga4': os.environ.get('GTAG_GA4', '')}


def gtag_ua_processor(request):
    return {'gtag_ua': os.environ.get('GTAG_UA', '')}