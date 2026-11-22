from django.conf import settings
from django.core.checks import Warning, register


@register()
def check_installed_apps(app_configs, **kwargs):
    apps = list(settings.INSTALLED_APPS)
    messages = []
    if "grappelli" not in apps:
        messages.append(
            Warning(
                "grappelli_theme_editor needs django-grappelli in INSTALLED_APPS.",
                id="grappelli_theme_editor.W001",
            )
        )
    elif apps.index("grappelli_theme_editor") > apps.index("grappelli"):
        messages.append(
            Warning(
                "grappelli_theme_editor is listed after grappelli, so its "
                "admin/base_site.html (which loads the theme stylesheet) is "
                "shadowed by Grappelli's.",
                hint="Put grappelli_theme_editor before grappelli, or add "
                "{% grappelli_theme_stylesheet %} to your own base_site.html.",
                id="grappelli_theme_editor.W002",
            )
        )
    if "django.template.context_processors.request" not in str(settings.TEMPLATES):
        messages.append(
            Warning(
                "The theme stylesheet tag needs the request context processor.",
                hint="Add django.template.context_processors.request.",
                id="grappelli_theme_editor.W003",
            )
        )
    return messages
