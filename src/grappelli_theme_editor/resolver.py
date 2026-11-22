"""Which theme does a request get? user preference > site default > none."""

from __future__ import annotations

from .models import Theme, UserThemePreference

_ATTR = "_grappelli_theme_editor_theme"
# Theme tried "for this session" (pk), shown instead of the saved choice.
SESSION_KEY = "grappelli_theme_editor_try"
DISABLE_ATTR = "_grappelli_theme_editor_disabled"


def tried_theme(request) -> Theme | None:
    """The theme tried in this session, if the user may still see it.

    Stale entries (deleted theme, access lost) are dropped from the session.
    """
    session = getattr(request, "session", None)
    if session is None:
        return None
    pk = session.get(SESSION_KEY)
    if not pk:
        return None
    theme = Theme.objects.filter(pk=pk).first()
    if theme is None or not theme.can_view(getattr(request, "user", None)):
        session.pop(SESSION_KEY, None)
        return None
    return theme


def get_active_theme(request) -> Theme | None:
    if request is None or getattr(request, DISABLE_ATTR, False):
        return None
    if hasattr(request, _ATTR):
        return getattr(request, _ATTR)
    theme = None
    user = getattr(request, "user", None)
    theme = tried_theme(request)
    if theme is None and user is not None and user.is_authenticated:
        pref = (
            UserThemePreference.objects.filter(user=user)
            .select_related("theme")
            .first()
        )
        if pref is not None and pref.theme is not None and pref.theme.can_view(user):
            theme = pref.theme
    if theme is None:
        theme = Theme.objects.filter(is_site_default=True).first()
    setattr(request, _ATTR, theme)
    return theme


def disable_for_request(request) -> None:
    """Used by the editor preview: the parent window injects the CSS."""
    setattr(request, DISABLE_ATTR, True)
