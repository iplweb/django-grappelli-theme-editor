from __future__ import annotations

import base64
import json

from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse, HttpResponseNotModified, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_http_methods

from . import conf, contrast, revisions
from .css import cached_theme_css_and_version, render_theme_css, theme_variables
from .forms import ThemeForm
from .models import Theme, ThemeFont, UserThemePreference
from .resolver import (
    SESSION_KEY,
    disable_for_request,
    get_active_theme,
    tried_theme,
)
from .tokens import MODES

YEAR = 60 * 60 * 24 * 365
IMAGE_MIME_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}


def _css_response(css: str, etag: str, request, cacheable: bool):
    """Versioned URLs may be cached for long, but never by shared caches.

    A theme's visibility can change (a shared theme may get an owner), so
    responses are always ``private``; private themes are revalidated on every
    use so a logged-out browser does not keep showing them.
    """
    quoted = f'"{etag}"'
    if request.headers.get("If-None-Match") == quoted:
        response = HttpResponseNotModified()
    else:
        response = HttpResponse(css, content_type="text/css; charset=utf-8")
    response["ETag"] = quoted
    if cacheable:
        response["Cache-Control"] = f"private, max-age={YEAR}, immutable"
    else:
        response["Cache-Control"] = "private, no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_GET
def theme_css(request, pk: int, version: str):
    theme = get_object_or_404(Theme, pk=pk)
    if not theme.can_view(request.user):
        raise Http404
    css, current = cached_theme_css_and_version(theme)
    return _css_response(
        css, current, request, cacheable=theme.is_shared and version == current
    )


def _sample_rows():
    return [
        {"title": _("Annual report %(n)s") % {"n": 2020 + i}, "n": i}
        for i in range(1, 7)
    ]


@staff_member_required
@require_GET
def preview(request):
    """A catalogue of Grappelli components, shown in the editor's iframe."""
    disable_for_request(request)
    context = {
        **admin.site.each_context(request),
        "title": _("Theme preview"),
        "rows": _sample_rows(),
    }
    return render(request, "grappelli_theme_editor/preview.html", context)


def _editable_theme(request, pk) -> Theme | None:
    if not pk:
        return None
    theme = get_object_or_404(Theme, pk=pk)
    if not theme.can_edit(request.user):
        raise PermissionDenied
    return theme


@staff_member_required
@require_http_methods(["POST"])
def preview_css(request):
    """Render CSS for the *unsaved* editor state (the whole admin form).

    The response also carries resolved colours (so the editor can show what
    the seed colours produced) and contrast warnings.
    """
    instance = _editable_theme(request, request.GET.get("theme")) or Theme()
    data = request.POST.copy()
    if not data.get("name"):
        data["name"] = "preview"
    form = ThemeForm(data=data, files=request.FILES, instance=instance)
    if not request.user.is_superuser:
        form.fields.pop("custom_css", None)
    # The preview never saves, so uniqueness/ownership don't matter here.
    for name in ("slug", "owner", "is_site_default"):
        form.fields.pop(name, None)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors}, status=200)
    theme = form.instance
    image_url = None
    upload = request.FILES.get("image")
    if upload is not None:
        # Not saved yet: inline it so the preview can show it.
        # The MIME type comes from the (already validated) extension, never
        # from the client's Content-Type, which ends up inside CSS.
        extension = upload.name.rsplit(".", 1)[-1].lower()
        mime = IMAGE_MIME_TYPES.get(extension, "image/png")
        image_url = f"data:{mime};base64," + base64.b64encode(upload.read()).decode(
            "ascii"
        )
    variables = {mode: theme_variables(theme, mode) for mode in MODES}
    return JsonResponse(
        {
            "ok": True,
            "css": render_theme_css(theme, image_url),
            "tokens": {
                mode: {k: v for k, v in values.items() if k.startswith("--grp-")}
                for mode, values in variables.items()
            },
            "contrast": contrast.warnings(variables, modes=_checked_modes(theme)),
        }
    )


def _checked_modes(theme: Theme) -> tuple[str, ...]:
    if theme.color_scheme == Theme.ColorScheme.USER:
        return MODES
    return (theme.color_scheme,)


def _swatches(theme: Theme) -> list[str]:
    mode = "dark" if theme.color_scheme == Theme.ColorScheme.DARK else "light"
    values = contrast.full_values(theme_variables(theme, mode), mode)
    names = [
        "--grp-dark-background-color",
        "--grp-body-background-color",
        "--grp-module-background-color",
        "--grp-link-color",
        "--grp-form-button-background-color",
        "--grp-font-color",
    ]
    return [contrast.resolve(values, n) or "transparent" for n in names]


@staff_member_required
@require_http_methods(["GET", "POST"])
def my_theme(request):
    user = request.user
    if request.method == "POST":
        action = request.POST.get("action")
        theme_id = request.POST.get("theme") or None
        if action == "choose":
            theme = None
            if theme_id:
                theme = get_object_or_404(Theme.objects.visible_to(user), pk=theme_id)
            UserThemePreference.objects.update_or_create(
                user=user, defaults={"theme": theme}
            )
            messages.success(request, _("Your appearance settings were saved."))
            return redirect("grappelli_theme_editor:my-theme")
        if action == "duplicate":
            if not conf.get("ALLOW_USER_THEMES"):
                raise PermissionDenied
            source = get_object_or_404(Theme.objects.visible_to(user), pk=theme_id)
            comment = _("Copied from “%(name)s”") % {"name": source.name}
            with revisions.revision(user, comment):
                copy = duplicate_theme(
                    source, owner=user, with_custom_css=user.is_superuser
                )
            return redirect("admin:grappelli_theme_editor_theme_change", copy.pk)
        raise Http404

    active = get_active_theme(request)
    pref = UserThemePreference.objects.filter(user=user).first()
    themes = list(Theme.objects.visible_to(user).select_related("owner"))
    context = {
        **admin.site.each_context(request),
        "title": _("Appearance"),
        "themes": [
            {
                "theme": t,
                "swatches": _swatches(t),
                "can_edit": t.can_edit(user),
                "selected": pref is not None and pref.theme_id == t.pk,
            }
            for t in themes
        ],
        "uses_default": pref is None or pref.theme_id is None,
        "site_default": next((t for t in themes if t.is_site_default), None),
        "active": active,
        "trying": tried_theme(request),
        "allow_user_themes": conf.get("ALLOW_USER_THEMES"),
    }
    return render(request, "grappelli_theme_editor/my_theme.html", context)


def duplicate_theme(source: Theme, owner=None, with_custom_css=False) -> Theme:
    """Copy a theme. Custom CSS (superuser-only) is copied only on request."""
    copy = Theme(
        **{f: getattr(source, f) for f in Theme.EXPORT_FIELDS},
        custom_css=source.custom_css if with_custom_css else "",
        image=source.image,
        owner=owner,
    )
    copy.name = _("%(name)s (copy)") % {"name": source.name}
    copy.save()
    return copy


def export_theme(theme: Theme, include_custom_css: bool = True) -> HttpResponse:
    payload = json.dumps(
        theme.to_dict(include_custom_css=include_custom_css),
        indent=2,
        ensure_ascii=False,
    )
    response = HttpResponse(payload, content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="{theme.slug}.json"'
    return response


@staff_member_required
@require_http_methods(["POST"])
def add_web_font(request):
    """Add a web font (stylesheet URL) from the editor's font menu.

    Superusers only: a stylesheet URL loads arbitrary remote CSS into the
    admin (and, for the site default, the login page) — as powerful as
    custom CSS.
    """
    if not request.user.is_superuser:
        raise PermissionDenied
    font = ThemeFont(
        family=request.POST.get("family", "").strip(),
        stylesheet_url=request.POST.get("stylesheet_url", "").strip(),
    )
    try:
        font.full_clean()
    except ValidationError as e:
        return JsonResponse({"ok": False, "errors": e.message_dict}, status=400)
    font.save()
    return JsonResponse({"ok": True, "family": font.family, "url": font.stylesheet_url})


def safe_next(request, default: str) -> str:
    """The ``next`` parameter if it points to this site, else ``default``."""
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return default


@staff_member_required
@require_http_methods(["POST"])
def try_theme(request, pk: int):
    """Show a theme for the rest of this browser session, without saving."""
    theme = get_object_or_404(Theme, pk=pk)
    if not theme.can_view(request.user):
        raise Http404
    request.session[SESSION_KEY] = theme.pk
    messages.info(
        request,
        _("You are trying “%(name)s” for this session only.") % {"name": theme.name},
    )
    return redirect(safe_next(request, reverse("grappelli_theme_editor:my-theme")))


@staff_member_required
@require_http_methods(["POST"])
def stop_trying(request):
    request.session.pop(SESSION_KEY, None)
    return redirect(safe_next(request, reverse("grappelli_theme_editor:my-theme")))
