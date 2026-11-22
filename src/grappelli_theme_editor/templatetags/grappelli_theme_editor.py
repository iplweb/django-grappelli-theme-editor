from django import template
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import format_html

from .. import conf
from ..resolver import get_active_theme

register = template.Library()


@register.simple_tag(takes_context=True)
def grappelli_theme_stylesheet(context):
    """``<link>`` to the active theme's stylesheet (or nothing).

    Put it in the ``extrastyle`` block of ``admin/base_site.html`` — the
    bundled template does that for you.
    """
    request = context.get("request")
    theme = get_active_theme(request)
    if theme is None:
        return ""
    url = reverse(
        "grappelli_theme_editor:theme-css",
        kwargs={"pk": theme.pk, "version": theme.version_hash()},
    )
    return format_html(
        '<link rel="stylesheet" type="text/css" href="{}" '
        'data-grappelli-theme="{}">'
        '<script src="{}" defer></script>',
        url,
        theme.slug,
        static("grappelli_theme_editor/header-offset.js"),
    )


@register.simple_tag(takes_context=True)
def grappelli_theme_user_link(context):
    if not conf.get("USER_TOOLS_LINK"):
        return ""
    request = context.get("request")
    user = getattr(request, "user", None)
    if user is None or not user.is_staff:
        return ""
    from django.utils.translation import gettext as _

    from ..resolver import tried_theme

    label = _("Appearance")
    if tried_theme(request) is not None:
        label = _("Appearance (trying)")
    return format_html(
        '<li><a href="{}">{}</a></li>',
        reverse("grappelli_theme_editor:my-theme"),
        label,
    )
