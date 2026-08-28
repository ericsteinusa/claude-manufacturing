from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # Django's built-in set_language view (POST target for the language
    # switcher in base.html) — sets the session language LocaleMiddleware
    # reads on every subsequent request.
    path('i18n/', include('django.conf.urls.i18n')),
    path('', include('manufacturing.urls')),
]
