from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Theme, ThemeFont

FONT_SUGGESTIONS = [
    "Arial, sans-serif",
    "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
    "'Helvetica Neue', Helvetica, Arial, sans-serif",
    "Verdana, Geneva, sans-serif",
    "Tahoma, Verdana, sans-serif",
    "'Trebuchet MS', sans-serif",
    "Georgia, 'Times New Roman', serif",
    "'Palatino Linotype', Palatino, serif",
    "ui-monospace, Menlo, Consolas, monospace",
]

JSON_FIELDS = ("seeds", "light_tokens", "dark_tokens", "components")


class FontFamilyInput(forms.TextInput):
    """Text input with a <datalist> of common stacks + uploaded fonts."""

    template_name = "grappelli_theme_editor/widgets/font_family.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        uploaded = sorted(set(ThemeFont.objects.values_list("family", flat=True)))
        context["widget"]["suggestions"] = [
            *(f'"{family}", sans-serif' for family in uploaded),
            *FONT_SUGGESTIONS,
        ]
        list_id = f"{(attrs or {}).get('id', name)}_suggestions"
        context["widget"]["list_id"] = list_id
        context["widget"]["attrs"]["list"] = list_id
        return context


class ThemeForm(forms.ModelForm):
    class Meta:
        model = Theme
        fields = "__all__"
        widgets = {
            **{name: forms.HiddenInput() for name in JSON_FIELDS},
            "font_sans": FontFamilyInput(attrs={"class": "vTextField"}),
            "font_mono": FontFamilyInput(attrs={"class": "vTextField"}),
            "font_heading": FontFamilyInput(attrs={"class": "vTextField"}),
            "font_label": FontFamilyInput(attrs={"class": "vTextField"}),
            "font_field": FontFamilyInput(attrs={"class": "vTextField"}),
            "font_scale": forms.NumberInput(attrs={"step": "0.05"}),
            "radius_scale": forms.NumberInput(attrs={"step": "0.25"}),
            "spacing_scale": forms.NumberInput(attrs={"step": "0.05"}),
            "description": forms.Textarea(attrs={"rows": 2}),
            "custom_css": forms.Textarea(
                attrs={"rows": 10, "class": "gte-code", "spellcheck": "false"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "web_font_provider" in self.fields:
            # Older clients/imports don't send it; fall back to the default.
            self.fields["web_font_provider"].required = False

    def clean_web_font_provider(self):
        return self.cleaned_data.get("web_font_provider") or "bunny"


class ThemeImportForm(forms.Form):
    file = forms.FileField(
        label=_("Theme file (.json)"),
        help_text=_("A file exported from this editor."),
    )
