from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("grappelli/", include("grappelli.urls")),
    path("admin/themes/", include("grappelli_theme_editor.urls")),
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("", RedirectView.as_view(url="/admin/")),
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]

try:
    from django_dev_helpers.urls import autologin_urlpatterns
except ImportError:
    pass
else:
    urlpatterns = [*autologin_urlpatterns(), *urlpatterns]
