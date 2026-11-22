from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models, transaction
from django.db.models import Q
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from . import conf, validators
from .components import validate_components


def _empty_seeds():
    return {"light": {}, "dark": {}}


def validate_upload_size(f, setting: str) -> None:
    limit = conf.get(setting)
    if f.size > limit:
        raise ValidationError(
            _("The file may be at most %(kb)d kB.") % {"kb": limit // 1024}
        )


# File signatures: the extension alone proves nothing, and a ".png" full of
# HTML could be served inline from the admin's origin.
IMAGE_SIGNATURES = (
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",
    b"GIF87a",
    b"GIF89a",
)
FONT_SIGNATURES = (b"wOF2", b"wOFF", b"\x00\x01\x00\x00", b"OTTO", b"true")


def _head(f, n: int = 12) -> bytes:
    position = f.tell() if hasattr(f, "tell") else 0
    f.seek(0)
    head = f.read(n)
    f.seek(position)
    return head


def validate_image_content(f) -> None:
    head = _head(f)
    is_webp = head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if not (is_webp or head.startswith(IMAGE_SIGNATURES)):
        raise ValidationError(_("This is not a PNG, JPEG, GIF or WebP image."))


def validate_font_content(f) -> None:
    if not _head(f, 4).startswith(FONT_SIGNATURES):
        raise ValidationError(_("This is not a WOFF2, WOFF, TTF or OTF font."))


def validate_font_size(f):
    validate_upload_size(f, "MAX_FONT_SIZE")


def validate_image_size(f):
    validate_upload_size(f, "MAX_IMAGE_SIZE")


class ThemeQuerySet(models.QuerySet):
    def shared(self):
        return self.filter(owner__isnull=True)

    def visible_to(self, user):
        if user is None or not user.is_authenticated:
            return self.shared()
        return self.filter(Q(owner__isnull=True) | Q(owner=user))


class Theme(models.Model):
    class ColorScheme(models.TextChoices):
        USER = "user", _("Follow the light/dark toggle")
        LIGHT = "light", _("Always light")
        DARK = "dark", _("Always dark")

    name = models.CharField(_("name"), max_length=100)
    slug = models.SlugField(_("slug"), max_length=100, unique=True, blank=True)
    description = models.TextField(_("description"), blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("owner"),
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="grappelli_themes",
        help_text=_("Empty = shared theme, available to everybody."),
    )
    is_site_default = models.BooleanField(
        _("site default"),
        default=False,
        help_text=_(
            "Used for everybody who has not picked a theme, including the "
            "login page. Only shared themes can be the site default."
        ),
    )
    color_scheme = models.CharField(
        _("light/dark mode"),
        max_length=8,
        choices=ColorScheme.choices,
        default=ColorScheme.USER,
    )
    seeds = models.JSONField(
        _("base colours"),
        default=_empty_seeds,
        blank=True,
        validators=[validators.validate_seeds],
    )
    light_tokens = models.JSONField(
        _("light mode overrides"),
        default=dict,
        blank=True,
        validators=[validators.validate_token_overrides],
    )
    dark_tokens = models.JSONField(
        _("dark mode overrides"),
        default=dict,
        blank=True,
        validators=[validators.validate_token_overrides],
    )
    components = models.JSONField(
        _("component styles"),
        default=dict,
        blank=True,
        help_text=_("Shapes, shadows, spacing and bars, see components.py."),
    )
    font_sans = models.CharField(
        _("interface font"),
        max_length=200,
        blank=True,
        validators=[validators.validate_font_family],
        help_text=_("CSS font-family list. Empty = Grappelli's Arial."),
    )
    font_mono = models.CharField(
        _("monospace font"),
        max_length=200,
        blank=True,
        validators=[validators.validate_font_family],
    )
    font_heading = models.CharField(
        _("headings font"),
        max_length=200,
        blank=True,
        validators=[validators.validate_font_family],
        help_text=_("Page titles and module headers. Empty = interface font."),
    )
    font_label = models.CharField(
        _("labels font"),
        max_length=200,
        blank=True,
        validators=[validators.validate_font_family],
        help_text=_("Form and filter labels. Empty = interface font."),
    )
    font_field = models.CharField(
        _("form fields font"),
        max_length=200,
        blank=True,
        validators=[validators.validate_font_family],
        help_text=_("Text inside inputs, selects and text areas."),
    )
    web_font_provider = models.CharField(
        _("web font service"),
        max_length=10,
        choices=[("bunny", "Bunny Fonts"), ("google", "Google Fonts")],
        default="bunny",
        help_text=_("Where the web fonts picked from the list are loaded from."),
    )
    font_scale = models.DecimalField(
        _("font size"),
        max_digits=3,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.80")), MaxValueValidator(1.6)],
        help_text=_("Multiplier for all font sizes, 1.00 = Grappelli default."),
    )
    radius_scale = models.DecimalField(
        _("corner rounding"),
        max_digits=3,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(0), MaxValueValidator(4)],
        help_text=_("0 = square corners, 1.00 = Grappelli default."),
    )
    spacing_scale = models.DecimalField(
        _("density"),
        max_digits=3,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.50")), MaxValueValidator(2)],
        help_text=_(
            "Multiplier for paddings: below 1.00 = more compact, above = airier."
        ),
    )
    image = models.FileField(
        _("background image"),
        upload_to="grappelli_theme_editor/images/",
        blank=True,
        validators=[
            FileExtensionValidator(["png", "jpg", "jpeg", "gif", "webp"]),
            validate_image_size,
            validate_image_content,
        ],
        help_text=_(
            "A small picture for the page background or the empty area next "
            "to tables; choose how it is placed under Shapes & bars."
        ),
    )
    custom_css = models.TextField(
        _("custom CSS"),
        blank=True,
        help_text=_("Appended verbatim. Only superusers can edit it."),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ThemeQuerySet.as_manager()

    class Meta:
        verbose_name = _("theme")
        verbose_name_plural = _("themes")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_site_default"],
                condition=Q(is_site_default=True),
                name="grappelli_theme_single_site_default",
            ),
            models.CheckConstraint(
                condition=Q(is_site_default=False) | Q(owner__isnull=True),
                name="grappelli_theme_site_default_is_shared",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        try:
            self.components = validate_components(self.components)
        except ValidationError as e:
            raise ValidationError({"components": e.messages}) from e
        if self.is_site_default and self.owner_id:
            raise ValidationError(
                {"is_site_default": _("A private theme cannot be the site default.")}
            )

    def validate_constraints(self, exclude=None):
        # save() moves the site default from the old theme to this one inside
        # a transaction; validating the single-default constraint first would
        # reject every switch made through a form. The database still
        # enforces it.
        exclude = set(exclude or ()) | {"is_site_default"}
        super().validate_constraints(exclude=exclude)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        if self.is_site_default:
            with transaction.atomic():
                Theme.objects.filter(is_site_default=True).exclude(pk=self.pk).update(
                    is_site_default=False
                )
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    def _unique_slug(self) -> str:
        base = slugify(self.name)[:90] or "theme"
        slug, n = base, 2
        while Theme.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug, n = f"{base}-{n}", n + 1
        return slug

    @property
    def is_shared(self) -> bool:
        return self.owner_id is None

    @property
    def font_fields(self) -> list[str]:
        return [
            self.font_sans,
            self.font_mono,
            self.font_heading,
            self.font_label,
            self.font_field,
        ]

    def tokens_for(self, mode: str) -> dict[str, str]:
        return self.light_tokens if mode == "light" else self.dark_tokens

    def version_hash(self) -> str:
        """Hash of the rendered stylesheet — changes whenever its bytes do."""
        from .css import cached_theme_css_and_version

        return cached_theme_css_and_version(self)[1]

    def can_view(self, user) -> bool:
        if self.is_shared:
            return True
        if user is None or not user.is_authenticated:
            return False
        return self.owner_id == user.pk or user.has_perm(
            "grappelli_theme_editor.view_theme"
        )

    def can_edit(self, user) -> bool:
        if user is None or not user.is_authenticated or not user.is_staff:
            return False
        if self.owner_id == user.pk:
            return True
        return user.has_perm("grappelli_theme_editor.change_theme")

    # Export / import -----------------------------------------------------

    EXPORT_FIELDS = (
        "name",
        "description",
        "color_scheme",
        "seeds",
        "light_tokens",
        "dark_tokens",
        "components",
        "font_sans",
        "font_mono",
        "font_heading",
        "font_label",
        "font_field",
        "web_font_provider",
        "font_scale",
        "radius_scale",
        "spacing_scale",
    )

    def to_dict(self, include_custom_css: bool = True) -> dict:
        out = {f: getattr(self, f) for f in self.EXPORT_FIELDS}
        out["font_scale"] = str(self.font_scale)
        out["radius_scale"] = str(self.radius_scale)
        out["spacing_scale"] = str(self.spacing_scale)
        if include_custom_css and self.custom_css:
            out["custom_css"] = self.custom_css
        out["format"] = "grappelli-theme-editor/1"
        return out

    def update_from_dict(self, data: dict, allow_custom_css: bool) -> None:
        if not isinstance(data, dict):
            raise ValidationError(_("The file does not contain a theme."))
        for field in self.EXPORT_FIELDS:
            if field in data:
                setattr(self, field, data[field])
        if allow_custom_css and "custom_css" in data:
            self.custom_css = data["custom_css"]


def _font_upload_to(instance, filename):
    return f"grappelli_theme_editor/fonts/{filename}"


class ThemeFont(models.Model):
    """A self-hosted font face, available to every theme by its family name."""

    class Style(models.TextChoices):
        NORMAL = "normal", _("normal")
        ITALIC = "italic", _("italic")

    family = models.CharField(
        _("family name"),
        max_length=100,
        validators=[validators.validate_font_family],
        help_text=_('Use this name in a theme\'s font field, e.g. "Inter".'),
    )
    file = models.FileField(
        _("font file"),
        upload_to=_font_upload_to,
        blank=True,
        validators=[
            FileExtensionValidator(["woff2", "woff", "ttf", "otf"]),
            validate_font_size,
            validate_font_content,
        ],
        help_text=_("Upload a font file (self-hosted)…"),
    )
    stylesheet_url = models.URLField(
        _("web font stylesheet URL"),
        blank=True,
        max_length=500,
        validators=[validators.validate_stylesheet_url],
        help_text=_(
            "…or link a web font stylesheet, e.g. "
            "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700"
            "&display=swap — then weight and style below are ignored."
        ),
    )
    weight = models.PositiveSmallIntegerField(
        _("weight"),
        default=400,
        validators=[MinValueValidator(100), MaxValueValidator(900)],
    )
    style = models.CharField(
        _("style"), max_length=8, choices=Style.choices, default=Style.NORMAL
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("font")
        verbose_name_plural = _("fonts")
        ordering = ["family", "weight", "style"]
        constraints = [
            models.UniqueConstraint(
                fields=["family", "weight", "style"],
                name="grappelli_theme_font_unique_face",
            )
        ]

    def __str__(self):
        if self.stylesheet_url:
            return f"{self.family} (web font)"
        return f"{self.family} {self.weight} {self.style}"

    def clean(self):
        super().clean()
        if bool(self.file) == bool(self.stylesheet_url):
            raise ValidationError(
                _("Upload a font file or enter a web font URL (exactly one).")
            )
        if self.stylesheet_url and not conf.get("ALLOW_WEB_FONTS"):
            raise ValidationError(
                {"stylesheet_url": _("Web fonts are disabled in the settings.")}
            )

    @property
    def css_format(self) -> str:
        if not self.file:
            return ""
        ext = self.file.name.rsplit(".", 1)[-1].lower()
        return {"ttf": "truetype", "otf": "opentype"}.get(ext, ext)


class UserThemePreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="grappelli_theme_preference",
    )
    theme = models.ForeignKey(
        Theme,
        verbose_name=_("theme"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text=_("Empty = use the site default."),
    )

    class Meta:
        verbose_name = _("user theme preference")
        verbose_name_plural = _("user theme preferences")

    def __str__(self):
        return f"{self.user}: {self.theme or '-'}"
