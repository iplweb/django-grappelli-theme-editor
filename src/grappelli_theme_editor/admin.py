from __future__ import annotations

import hashlib
import json
from functools import cache
from pathlib import Path

from django.contrib import admin, messages
from django.contrib.admin.utils import flatten_fieldsets
from django.contrib.staticfiles import finders
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from . import conf, revisions
from .components import editor_schema
from .forms import FONT_SUGGESTIONS, JSON_FIELDS, ThemeForm, ThemeImportForm
from .models import Theme, ThemeFont, UserThemePreference
from .palette import SEEDS, seed_defaults
from .resolver import tried_theme
from .tokens import DARK, LIGHT, grouped_color_tokens
from .views import _swatches, duplicate_theme, export_theme, safe_next
from .webfonts import (
    GOOGLE_FONTS,
    PROVIDERS,
    allowed_providers,
    font_stack,
    web_font_url,
)


@cache
def asset_version() -> str:
    """Content hash of the editor's JS/CSS, appended as ?v= to bust caches.

    Without it browsers happily keep a stale editor.js after an upgrade
    (Django's static view and most servers send no Cache-Control).
    """
    digest = hashlib.sha1()
    for name in ("editor.js", "editor.css"):
        path = finders.find(f"grappelli_theme_editor/{name}")
        if path:
            digest.update(Path(path).read_bytes())
    return digest.hexdigest()[:10]


def _privileged(request) -> bool:
    return request.user.has_perm("grappelli_theme_editor.change_theme")


if revisions.enabled():
    from reversion.admin import VersionAdmin as BaseThemeAdmin
else:
    BaseThemeAdmin = admin.ModelAdmin


@admin.register(Theme)
class ThemeAdmin(BaseThemeAdmin):
    form = ThemeForm
    change_form_template = "admin/grappelli_theme_editor/theme/change_form.html"
    # django-reversion: show the editor (and the live preview of the old
    # version) when reverting or recovering.
    revision_form_template = change_form_template
    recover_form_template = change_form_template
    change_list_template = "admin/grappelli_theme_editor/theme/change_list.html"
    list_display = (
        "name",
        "palette",
        "owner",
        "site_default_button",
        "color_scheme",
        "updated_at",
    )
    list_filter = (
        "is_site_default",
        "color_scheme",
        ("owner", admin.EmptyFieldListFilter),
    )
    search_fields = ("name", "description")
    actions = ("make_site_default", "duplicate", "export_json")
    readonly_fields = ()

    # Permissions: users with model permissions manage everything; other
    # staff members (when ALLOW_USER_THEMES) see shared themes read-only and
    # fully manage their own private ones.

    def _user_themes(self, request) -> bool:
        return conf.get("ALLOW_USER_THEMES") and request.user.is_staff

    def has_module_permission(self, request):
        return super().has_module_permission(request) or self._user_themes(request)

    def has_view_permission(self, request, obj=None):
        if super().has_view_permission(request, obj):
            return True
        if not self._user_themes(request):
            return False
        return obj is None or obj.is_shared or obj.owner_id == request.user.pk

    def has_add_permission(self, request):
        return super().has_add_permission(request) or self._user_themes(request)

    def has_change_permission(self, request, obj=None):
        if super().has_change_permission(request, obj):
            return True
        if not self._user_themes(request):
            return False
        return obj is None or obj.owner_id == request.user.pk

    def has_delete_permission(self, request, obj=None):
        if super().has_delete_permission(request, obj):
            return True
        if not self._user_themes(request):
            return False
        return obj is not None and obj.owner_id == request.user.pk

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("owner")
        if request.user.has_perm("grappelli_theme_editor.view_theme"):
            return qs
        return qs.filter(Q(owner__isnull=True) | Q(owner=request.user))

    def has_manage_permission(self, request):
        """Used by actions only theme managers may run (site default)."""
        return _privileged(request)

    # Form ---------------------------------------------------------------

    def get_fieldsets(self, request, obj=None):
        general = ["name", "description", "color_scheme"]
        if _privileged(request):
            general[1:1] = ["slug"]
            general += ["owner", "is_site_default"]
        fieldsets = [
            (None, {"fields": general}),
            (
                _("Typography & sizes"),
                {
                    "fields": [
                        "font_sans",
                        "font_heading",
                        "font_label",
                        "font_field",
                        "font_mono",
                        "web_font_provider",
                        ("font_scale", "radius_scale", "spacing_scale"),
                    ],
                    "description": _(
                        "Fonts must be installed on the viewer's computer or "
                        "uploaded under Admin themes › Fonts."
                    ),
                },
            ),
            (
                _("Background image"),
                {"fields": ["image"], "classes": ("gte-image-fieldset",)},
            ),
            (None, {"fields": list(JSON_FIELDS), "classes": ("gte-data",)}),
        ]
        if request.user.is_superuser:
            fieldsets.append(
                (
                    _("Custom CSS"),
                    {
                        "fields": ["custom_css"],
                        "classes": ("grp-collapse", "grp-closed"),
                    },
                )
            )
        return fieldsets

    def get_form(self, request, obj=None, change=False, **kwargs):
        kwargs["fields"] = flatten_fieldsets(self.get_fieldsets(request, obj))
        return super().get_form(request, obj, change, **kwargs)

    def save_model(self, request, obj, form, change):
        if not _privileged(request):
            if not change:
                obj.owner = request.user
            obj.is_site_default = False
        super().save_model(request, obj, form, change)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = {
            **(extra_context or {}),
            **self._editor_context(request, object_id),
        }
        return super().changeform_view(request, object_id, form_url, extra_context)

    def _editor_context(self, request, object_id=None) -> dict:
        defaults = {LIGHT: seed_defaults(LIGHT), DARK: seed_defaults(DARK)}
        return {
            "gte_seeds": [
                {
                    "key": s.key,
                    "label": s.label,
                    "light": defaults[LIGHT][s.key],
                    "dark": defaults[DARK][s.key],
                    "derive_dark": s.derive_dark,
                }
                for s in SEEDS
            ],
            "gte_token_groups": grouped_color_tokens(),
            "gte_components": editor_schema(),
            "gte_prop_types": {
                c["key"]: {p["key"]: p["type"] for p in c["props"]}
                for c in editor_schema()
            },
            "gte_sources": [
                {
                    "pk": t.pk,
                    "name": t.name,
                    "data": t.to_dict(include_custom_css=False),
                }
                for t in Theme.objects.visible_to(request.user)
                .exclude(pk=object_id or None)
                .order_by("name")
            ],
            "gte_fonts_url": reverse(
                "admin:grappelli_theme_editor_themefont_changelist"
            ),
            "gte_font_picker": {
                "system": [
                    {"label": stack.split(",")[0].strip("'\" "), "value": stack}
                    for stack in FONT_SUGGESTIONS
                ],
                "uploaded": [
                    {
                        "family": f.family,
                        "web": bool(f.stylesheet_url),
                        "url": f.stylesheet_url,
                    }
                    for f in ThemeFont.objects.order_by("family", "weight")
                ],
                "web": [
                    {
                        "key": key,
                        "name": PROVIDERS[key][0],
                        "host": PROVIDERS[key][1].removeprefix("https://"),
                        "families": [
                            {
                                "family": name,
                                "value": font_stack(name),
                                "url": web_font_url(name, key),
                            }
                            for name, _cat, _w in GOOGLE_FONTS
                        ],
                    }
                    for key in allowed_providers()
                ],
                "canAddWebFont": request.user.is_superuser
                and conf.get("ALLOW_WEB_FONTS"),
                "addWebFontUrl": reverse("grappelli_theme_editor:add-web-font"),
            },
            "gte_asset_version": asset_version(),
            "gte_privileged": _privileged(request),
            "gte_trying": getattr(tried_theme(request), "pk", None),
            "gte_preview_url": reverse("grappelli_theme_editor:preview"),
            "gte_preview_css_url": reverse("grappelli_theme_editor:preview-css"),
            "gte_i18n": {
                "updating": gettext("Updating…"),
                "failed": gettext("Preview failed: "),
                "lowContrast": gettext(
                    "Low contrast (%(mode)s): %(label)s — %(ratio)s:1, "
                    "needs %(minimum)s:1"
                ),
                "light": gettext("light"),
                "dark": gettext("dark"),
                "baseColours": gettext("Base colours"),
                "components": gettext("Shapes & bars"),
                "tokens": gettext("Colour tokens"),
                "nothing": gettext("Nothing in this theme changes this element."),
                "taken": gettext("Taken from “%(name)s” — not saved yet."),
                "noLocalFonts": gettext(
                    "This browser cannot list installed fonts (only Chrome and "
                    "Edge can). Type the font name into the field instead."
                ),
                "localDenied": gettext("Permission to read local fonts was denied."),
                "choose": gettext("Choose…"),
                "filterFonts": gettext("Search fonts…"),
                "systemFonts": gettext("Safe system fonts — no downloads"),
                "yourFonts": gettext("Your fonts"),
                "webFonts": gettext("Web fonts from %(name)s"),
                "webWarning": gettext(
                    "⚠ Picking one makes every admin user's browser download it "
                    "from %(host)s."
                ),
                "showPreviews": gettext("Show previews (contacts %(host)s now)"),
                "localFonts": gettext("Fonts on this computer"),
                "detectLocal": gettext(
                    "Detect installed fonts (Chrome/Edge; others may not have them)"
                ),
                "addWebFont": gettext("Add another web font by URL…"),
                "family": gettext("Family name"),
                "cssUrl": gettext("Stylesheet URL (https://…)"),
                "add": gettext("Add"),
                "webBadge": gettext("web"),
                "webInUse": gettext(
                    "⚠ Web font in use (%(fonts)s): every admin user's browser "
                    "downloads it from %(hosts)s, a third-party server. For a fully "
                    "self-hosted admin, download the font and upload the files "
                    "under Fonts."
                ),
                "googleNote": gettext(
                    "Google receives the users' IP addresses — in the EU this may "
                    "need consent (GDPR)."
                ),
            },
        }

    # List display -------------------------------------------------------

    @admin.display(description=_("colours"))
    def palette(self, obj):
        return format_html(
            '<span class="gte-swatches">{}</span>',
            format_html_join(
                "",
                '<span class="gte-swatch" style="background:{}"></span>',
                ((c,) for c in _swatches(obj)),
            ),
        )

    @admin.display(description=_("site default"), boolean=True)
    def site_default_button(self, obj):
        """Static fallback; get_list_display() swaps in the per-request button."""
        return obj.is_site_default

    def get_list_display(self, request):
        privileged = _privileged(request)

        # Built per request (ModelAdmin is shared between threads).
        @admin.display(description=_("site default"))
        def site_default_button(obj):
            if obj.is_site_default:
                return format_html(
                    '<span class="gte-default-badge">★ {}</span>', _("Site default")
                )
            if not obj.is_shared or not privileged:
                return "–"
            # formaction: the change list is already a form (with the CSRF
            # token), and forms cannot be nested.
            return format_html(
                '<button type="submit" class="gte-row-button" formmethod="post" '
                'formaction="{}">☆ {}</button>',
                reverse(
                    "admin:grappelli_theme_editor_theme_make_default", args=[obj.pk]
                ),
                _("Make site default"),
            )

        return [
            site_default_button if name == "site_default_button" else name
            for name in super().get_list_display(request)
        ]

    def changelist_view(self, request, extra_context=None):
        extra_context = {
            **(extra_context or {}),
            "gte_reversion": revisions.enabled(),
            "gte_privileged": _privileged(request),
        }
        return super().changelist_view(request, extra_context)

    # Actions ------------------------------------------------------------

    @admin.action(
        description=_("Make the selected theme the site default"),
        permissions=["manage"],
    )
    def make_site_default(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request, _("Select exactly one theme."), level=messages.ERROR
            )
            return
        self._make_default(request, queryset.get())

    def _make_default(self, request, theme):
        if not theme.is_shared:
            self.message_user(
                request,
                _("A private theme cannot be the site default."),
                level=messages.ERROR,
            )
            return
        with revisions.revision(request.user, gettext("Made the site default")):
            theme.is_site_default = True
            theme.save()
        self.message_user(
            request, _("“%(name)s” is now the site default.") % {"name": theme.name}
        )

    # django-reversion ------------------------------------------------------
    #
    # Reverting applies a whole revision, which may contain other themes
    # (e.g. bulk copies) and fields the form hides (custom CSS). Check all of
    # it before django-reversion touches the database.

    def _check_revision(self, request, version):
        from reversion.models import Version

        for item in Version.objects.filter(revision_id=version.revision_id):
            if item.content_type.model_class() is not Theme:
                continue
            current = Theme.objects.filter(pk=item.object_id).first()
            if current is None:
                if not _privileged(request):
                    raise PermissionDenied  # recreating a deleted theme
            elif not self.has_change_permission(request, current):
                raise PermissionDenied
            historical_css = item.field_dict.get("custom_css") or ""
            current_css = current.custom_css if current is not None else ""
            if historical_css != current_css and not request.user.is_superuser:
                raise PermissionDenied  # custom CSS is superuser-only

    def _swapping_default(self, request, version, view):
        """Run a revert/recover view; a historical site default may need the
        slot another theme holds now. The swap is rolled back unless the
        revert is actually saved."""
        historical_default = version.field_dict.get("is_site_default")
        with transaction.atomic():
            if historical_default:
                Theme.objects.filter(is_site_default=True).exclude(
                    pk=version.object_id
                ).update(is_site_default=False)
            response = view()
            if not (request.method == "POST" and response.status_code == 302):
                transaction.set_rollback(True)
        return response

    def revision_view(self, request, object_id, version_id, extra_context=None):
        from reversion.models import Version

        version = get_object_or_404(Version, pk=version_id, object_id=object_id)
        self._check_revision(request, version)
        return self._swapping_default(
            request,
            version,
            lambda: super(ThemeAdmin, self).revision_view(
                request, object_id, version_id, extra_context
            ),
        )

    # Recovering deleted themes needs the model permissions (deleted versions
    # include other users' private themes).
    def recoverlist_view(self, request, extra_context=None):
        if not _privileged(request):
            raise PermissionDenied
        return super().recoverlist_view(request, extra_context)

    def recover_view(self, request, version_id, extra_context=None):
        from reversion.models import Version

        if not _privileged(request):
            raise PermissionDenied
        version = get_object_or_404(Version, pk=version_id)
        self._check_revision(request, version)
        return self._swapping_default(
            request,
            version,
            lambda: super(ThemeAdmin, self).recover_view(
                request, version_id, extra_context
            ),
        )

    def make_default_view(self, request, pk):
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        if not _privileged(request):
            raise PermissionDenied
        theme = get_object_or_404(self.get_queryset(request), pk=pk)
        self._make_default(request, theme)
        return redirect(
            safe_next(
                request,
                reverse("admin:grappelli_theme_editor_theme_change", args=[theme.pk]),
            )
        )

    @admin.action(description=_("Duplicate selected themes"), permissions=["add"])
    def duplicate(self, request, queryset):
        owner = None if _privileged(request) else request.user
        for theme in queryset:
            if not theme.can_view(request.user):
                raise PermissionDenied
            duplicate_theme(
                theme, owner=owner, with_custom_css=request.user.is_superuser
            )
        self.message_user(request, _("Themes duplicated."))

    @admin.action(description=_("Export the selected theme (JSON)"))
    def export_json(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request, _("Select exactly one theme."), level=messages.ERROR
            )
            return None
        return export_theme(queryset.get(), request.user.is_superuser)

    # Extra views --------------------------------------------------------

    def get_urls(self):
        prefix = f"{self.opts.app_label}_{self.opts.model_name}"
        return [
            path(
                "import/",
                self.admin_site.admin_view(self.import_view),
                name=f"{prefix}_import",
            ),
            path(
                "<int:pk>/make-default/",
                self.admin_site.admin_view(self.make_default_view),
                name=f"{prefix}_make_default",
            ),
            path(
                "<int:pk>/export/",
                self.admin_site.admin_view(self.export_view),
                name=f"{prefix}_export",
            ),
            *super().get_urls(),
        ]

    def export_view(self, request, pk):
        theme = get_object_or_404(self.get_queryset(request), pk=pk)
        if not self.has_view_permission(request, theme):
            raise PermissionDenied
        return export_theme(theme, request.user.is_superuser)

    def import_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        form = ThemeImportForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            try:
                data = json.loads(form.cleaned_data["file"].read().decode("utf-8"))
                theme = Theme(owner=None if _privileged(request) else request.user)
                theme.update_from_dict(data, allow_custom_css=request.user.is_superuser)
                theme.full_clean(exclude=["slug"])
                theme.save()
            except (UnicodeDecodeError, json.JSONDecodeError):
                form.add_error("file", gettext("This is not a JSON file."))
            except ValidationError as e:
                messages_ = (
                    [
                        f"{field}: {' '.join(errs)}"
                        for field, errs in e.message_dict.items()
                    ]
                    if hasattr(e, "error_dict")
                    else e.messages
                )
                form.add_error(None, messages_)
            except (TypeError, ValueError) as e:
                # Wrong JSON types (e.g. a list where a number is expected).
                form.add_error(
                    None, gettext("Invalid theme file: %(error)s") % {"error": e}
                )
            else:
                self.message_user(
                    request, _("Imported “%(name)s”.") % {"name": theme.name}
                )
                return redirect("admin:grappelli_theme_editor_theme_change", theme.pk)
        context = {
            **self.admin_site.each_context(request),
            "opts": self.opts,
            "title": _("Import theme"),
            "form": form,
        }
        return render(
            request, "admin/grappelli_theme_editor/theme/import.html", context
        )


@admin.register(ThemeFont)
class ThemeFontAdmin(admin.ModelAdmin):
    list_display = ("family", "weight", "style", "file", "stylesheet_url")
    list_filter = ("style",)
    search_fields = ("family",)

    def get_readonly_fields(self, request, obj=None):
        # A stylesheet URL injects arbitrary remote CSS: superusers only —
        # including renaming such a font (themes find fonts by family name).
        if request.user.is_superuser:
            return ()
        if obj is not None and obj.stylesheet_url:
            return ("family", "file", "stylesheet_url", "weight", "style")
        return ("stylesheet_url",)


@admin.register(UserThemePreference)
class UserThemePreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "theme")
    list_select_related = ("user", "theme")
    autocomplete_fields = ()
    raw_id_fields = ("user",)
