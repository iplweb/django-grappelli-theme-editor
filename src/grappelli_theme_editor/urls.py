from django.urls import path

from . import views

app_name = "grappelli_theme_editor"

urlpatterns = [
    path("theme/<int:pk>/<str:version>.css", views.theme_css, name="theme-css"),
    path("preview/", views.preview, name="preview"),
    path("preview/css/", views.preview_css, name="preview-css"),
    path("me/", views.my_theme, name="my-theme"),
    path("try/<int:pk>/", views.try_theme, name="try"),
    path("try/stop/", views.stop_trying, name="stop-trying"),
    path("fonts/add/", views.add_web_font, name="add-web-font"),
]
