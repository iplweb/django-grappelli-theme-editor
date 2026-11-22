"""Optional django-reversion support.

When ``reversion`` is in INSTALLED_APPS the theme admin is a ``VersionAdmin``
(history with revert, recover deleted themes) and changes made outside the
admin form — "Make site default", presets, "Customise a copy" — are recorded
as revisions too.
"""

from __future__ import annotations

from contextlib import contextmanager, nullcontext

from django.apps import apps


def enabled() -> bool:
    return apps.is_installed("reversion")


@contextmanager
def revision(user=None, comment: str = ""):
    """Record the saves in the block as one revision (no-op without reversion)."""
    if not enabled():
        with nullcontext():
            yield
        return
    import reversion

    with reversion.create_revision():
        if user is not None and getattr(user, "is_authenticated", False):
            reversion.set_user(user)
        if comment:
            reversion.set_comment(comment)
        yield


def register_models() -> None:
    if not enabled():
        return
    import reversion

    from .models import Theme, ThemeFont

    for model in (Theme, ThemeFont):
        if not reversion.is_registered(model):
            reversion.register(model)
