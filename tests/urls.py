from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("grappelli/", include("grappelli.urls")),
    path("admin/themes/", include("grappelli_theme_editor.urls")),
    path("admin/", admin.site.urls),
]
