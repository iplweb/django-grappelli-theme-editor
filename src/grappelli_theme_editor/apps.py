from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class GrappelliThemeEditorConfig(AppConfig):
    name = "grappelli_theme_editor"
    verbose_name = _("Admin themes")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import checks  # noqa: F401  (registers system checks)
        from .revisions import register_models

        register_models()
