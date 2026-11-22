import io
import json

import pytest
from django.urls import reverse

from grappelli_theme_editor.models import Theme

ADD = "admin:grappelli_theme_editor_theme_add"


def form_data(**extra):
    data = {
        "name": "Mine",
        "description": "",
        "color_scheme": "user",
        "seeds": json.dumps({"light": {"accent": "#123456"}, "dark": {}}),
        "light_tokens": "{}",
        "dark_tokens": "{}",
        "components": json.dumps({"tables": {"stripes": "off"}}),
        "font_sans": "",
        "font_mono": "",
        "font_scale": "1.00",
        "radius_scale": "1.00",
        "spacing_scale": "1.00",
    }
    data.update(extra)
    return data


@pytest.mark.django_db
def test_superuser_sees_editor(admin_client, shared_theme):
    r = admin_client.get(
        reverse("admin:grappelli_theme_editor_theme_change", args=[shared_theme.pk])
    )
    assert r.status_code == 200
    html = r.content.decode()
    assert 'id="gte-editor"' in html
    assert 'data-comp="buttons"' in html
    assert 'name="custom_css"' in html


@pytest.mark.django_db
def test_staff_user_creates_private_theme(staff_client, staff_user):
    r = staff_client.get(reverse(ADD))
    assert r.status_code == 200
    html = r.content.decode()
    assert 'name="custom_css"' not in html
    assert 'name="is_site_default"' not in html

    r = staff_client.post(reverse(ADD), form_data(is_site_default="on"))
    assert r.status_code == 302, r.content
    theme = Theme.objects.get()
    assert theme.owner == staff_user
    assert not theme.is_site_default
    assert theme.components == {"tables": {"stripes": "off"}}


@pytest.mark.django_db
def test_staff_user_cannot_edit_shared_theme(staff_client, shared_theme):
    url = reverse("admin:grappelli_theme_editor_theme_change", args=[shared_theme.pk])
    assert staff_client.get(url).status_code == 200  # read-only view
    r = staff_client.post(url, form_data(name="Hacked"))
    assert r.status_code == 403
    shared_theme.refresh_from_db()
    assert shared_theme.name == "Shared"


@pytest.mark.django_db
def test_staff_user_does_not_see_other_private_themes(staff_client, django_user_model):
    other = django_user_model.objects.create_user("other", is_staff=True)
    Theme.objects.create(name="Theirs", owner=other)
    r = staff_client.get(reverse("admin:grappelli_theme_editor_theme_changelist"))
    assert b"Theirs" not in r.content


@pytest.mark.django_db
def test_manager_can_set_site_default(client, theme_manager, shared_theme):
    client.force_login(theme_manager)
    r = client.post(
        reverse("admin:grappelli_theme_editor_theme_changelist"),
        {"action": "make_site_default", "_selected_action": [shared_theme.pk]},
    )
    assert r.status_code == 302
    shared_theme.refresh_from_db()
    assert shared_theme.is_site_default


@pytest.mark.django_db
def test_export_and_import(admin_client, shared_theme):
    r = admin_client.get(
        reverse("admin:grappelli_theme_editor_theme_export", args=[shared_theme.pk])
    )
    assert r.status_code == 200
    payload = r.content
    upload = io.BytesIO(payload)
    upload.name = "theme.json"
    r = admin_client.post(
        reverse("admin:grappelli_theme_editor_theme_import"), {"file": upload}
    )
    assert r.status_code == 302
    assert Theme.objects.filter(name="Shared").count() == 2


@pytest.mark.django_db
def test_import_rejects_invalid_file(admin_client):
    upload = io.BytesIO(b"not json")
    upload.name = "theme.json"
    r = admin_client.post(
        reverse("admin:grappelli_theme_editor_theme_import"), {"file": upload}
    )
    assert r.status_code == 200
    assert b"not a JSON file" in r.content


@pytest.mark.django_db
def test_read_only_view_has_no_editor(staff_client, shared_theme):
    r = staff_client.get(
        reverse("admin:grappelli_theme_editor_theme_change", args=[shared_theme.pk])
    )
    assert r.status_code == 200
    assert b'id="gte-editor"' not in r.content
    assert reverse("grappelli_theme_editor:my-theme").encode() in r.content


@pytest.mark.django_db
def test_import_with_wrong_types_shows_error(admin_client):
    upload = io.BytesIO(json.dumps({"name": "x", "font_scale": "2"}).encode())
    upload.name = "theme.json"
    r = admin_client.post(
        reverse("admin:grappelli_theme_editor_theme_import"), {"file": upload}
    )
    assert r.status_code == 200
    assert b"font_scale" in r.content


@pytest.mark.django_db
def test_duplicate_needs_add_permission(client, django_user_model, settings):
    from django.contrib.auth.models import Permission

    settings.GRAPPELLI_THEME_EDITOR = {"ALLOW_USER_THEMES": False}
    viewer = django_user_model.objects.create_user("viewer", is_staff=True)
    viewer.user_permissions.add(Permission.objects.get(codename="view_theme"))
    other = django_user_model.objects.create_user("other", is_staff=True)
    theirs = Theme.objects.create(name="Theirs", owner=other, custom_css="x{}")
    client.force_login(viewer)
    client.post(
        reverse("admin:grappelli_theme_editor_theme_changelist"),
        {"action": "duplicate", "_selected_action": [theirs.pk]},
    )
    assert Theme.objects.count() == 1


@pytest.mark.django_db
def test_make_default_button(client, theme_manager, shared_theme, staff_client):
    other = Theme.objects.create(name="Other", is_site_default=True)
    url = reverse(
        "admin:grappelli_theme_editor_theme_make_default", args=[shared_theme.pk]
    )
    assert staff_client.post(url).status_code == 403  # no model permissions
    client.force_login(theme_manager)
    assert client.get(url).status_code == 405
    r = client.post(url)
    assert r.status_code == 302
    shared_theme.refresh_from_db()
    other.refresh_from_db()
    assert shared_theme.is_site_default and not other.is_site_default
    # the change list offers the button for the other theme
    html = client.get(reverse("admin:grappelli_theme_editor_theme_changelist")).content
    assert b"gte-row-button" in html and b"Site default" in html


@pytest.mark.django_db
def test_reversion_records_and_reverts(admin_client, shared_theme):
    from reversion.models import Version

    url = reverse("admin:grappelli_theme_editor_theme_change", args=[shared_theme.pk])
    data = form_data(name="Shared", slug=shared_theme.slug)
    data["seeds"] = json.dumps({"light": {"accent": "#ff0000"}, "dark": {}})
    assert admin_client.post(url, data).status_code == 302
    data["seeds"] = json.dumps({"light": {"accent": "#00ff00"}, "dark": {}})
    assert admin_client.post(url, data).status_code == 302
    versions = Version.objects.get_for_object(shared_theme)
    assert versions.count() == 2
    oldest = versions.last()
    revert_url = reverse(
        "admin:grappelli_theme_editor_theme_revision",
        args=[shared_theme.pk, oldest.pk],
    )
    r = admin_client.get(revert_url)
    assert r.status_code == 200
    html = r.content.decode()
    assert 'id="gte-editor"' in html  # the editor, with the old version
    assert "#ff0000" in html
    assert "gte-revert-note" in html


@pytest.mark.django_db
def test_only_managers_recover_deleted_themes(staff_client, client, theme_manager):
    url = reverse("admin:grappelli_theme_editor_theme_recoverlist")
    assert staff_client.get(url).status_code == 403
    client.force_login(theme_manager)
    assert client.get(url).status_code == 200


def _revision_url(theme, version):
    return reverse(
        "admin:grappelli_theme_editor_theme_revision", args=[theme.pk, version.pk]
    )


@pytest.mark.django_db
def test_revert_refuses_revisions_touching_other_users_themes(
    staff_client, staff_user, django_user_model
):
    import reversion
    from reversion.models import Version

    other = django_user_model.objects.create_user("other", is_staff=True)
    with reversion.create_revision():
        mine = Theme.objects.create(name="Mine", owner=staff_user)
        theirs = Theme.objects.create(name="Theirs v1", owner=staff_user)
    theirs.owner = other
    theirs.name = "Theirs v2"
    theirs.save()
    version = Version.objects.get_for_object(mine).first()
    assert staff_client.get(_revision_url(mine, version)).status_code == 403
    theirs.refresh_from_db()
    assert theirs.name == "Theirs v2"


@pytest.mark.django_db
def test_revert_cannot_restore_custom_css_for_non_superusers(
    staff_client, staff_user, admin_client
):
    import reversion
    from reversion.models import Version

    with reversion.create_revision():
        theme = Theme.objects.create(name="Mine", owner=staff_user, custom_css="a{}")
    theme.custom_css = ""
    theme.save()
    version = Version.objects.get_for_object(theme).first()
    assert staff_client.get(_revision_url(theme, version)).status_code == 403
    assert admin_client.get(_revision_url(theme, version)).status_code == 200


@pytest.mark.django_db
def test_reverting_to_a_former_site_default(admin_client):
    import reversion
    from reversion.models import Version

    with reversion.create_revision():
        a = Theme.objects.create(name="A", is_site_default=True)
    b = Theme.objects.create(name="B")
    b.is_site_default = True
    b.save()
    version = Version.objects.get_for_object(a).first()
    url = _revision_url(a, version)
    assert admin_client.get(url).status_code == 200
    b.refresh_from_db()
    assert b.is_site_default  # viewing rolled the swap back
    data = form_data(name="A", slug=a.slug, is_site_default="on")
    assert admin_client.post(url, data).status_code == 302
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.is_site_default and not b.is_site_default


@pytest.mark.django_db
def test_url_fonts_are_read_only_for_non_superusers(client, theme_manager):
    from grappelli_theme_editor.models import ThemeFont

    font = ThemeFont.objects.create(
        family="Remote", stylesheet_url="https://x.example/a.css"
    )
    client.force_login(theme_manager)
    url = reverse("admin:grappelli_theme_editor_themefont_change", args=[font.pk])
    client.post(url, {"family": "Inter"})
    font.refresh_from_db()
    assert font.family == "Remote"
