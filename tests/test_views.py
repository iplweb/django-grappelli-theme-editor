import json

import pytest
from django.urls import reverse

from grappelli_theme_editor.models import Theme, UserThemePreference


def css_url(theme):
    return reverse(
        "grappelli_theme_editor:theme-css",
        kwargs={"pk": theme.pk, "version": theme.version_hash()},
    )


@pytest.mark.django_db
def test_theme_css_is_public_cacheable_for_shared(client, shared_theme):
    r = client.get(css_url(shared_theme))
    assert r.status_code == 200
    assert r["Content-Type"].startswith("text/css")
    assert "immutable" in r["Cache-Control"]
    assert r["Cache-Control"].startswith("private")  # never shared caches
    assert "--grp-link-color:#8e44ad" in r.content.decode()

    again = client.get(css_url(shared_theme), HTTP_IF_NONE_MATCH=r["ETag"])
    assert again.status_code == 304


@pytest.mark.django_db
def test_stale_version_is_not_cached_forever(client, shared_theme):
    url = reverse(
        "grappelli_theme_editor:theme-css",
        kwargs={"pk": shared_theme.pk, "version": "old"},
    )
    r = client.get(url)
    assert r.status_code == 200
    assert r["Cache-Control"] == "private, no-cache"


@pytest.mark.django_db
def test_private_theme_css_is_hidden_from_others(client, staff_user, django_user_model):
    theme = Theme.objects.create(name="Mine", owner=staff_user)
    assert client.get(css_url(theme)).status_code == 404
    other = django_user_model.objects.create_user("other", is_staff=True)
    client.force_login(other)
    assert client.get(css_url(theme)).status_code == 404
    client.force_login(staff_user)
    r = client.get(css_url(theme))
    assert r.status_code == 200
    assert r["Cache-Control"] == "private, no-cache"  # revalidate private themes


@pytest.mark.django_db
def test_admin_pages_link_the_active_theme(admin_client):
    r = admin_client.get("/admin/")
    assert b"data-grappelli-theme" not in r.content  # nothing active yet

    site = Theme.objects.create(name="Site", is_site_default=True)
    r = admin_client.get("/admin/")
    assert css_url(site).encode() in r.content
    assert b"header-offset.js" in r.content
    # the user-tools link
    assert reverse("grappelli_theme_editor:my-theme").encode() in r.content


@pytest.mark.django_db
def test_login_page_uses_site_default(client):
    site = Theme.objects.create(name="Site", is_site_default=True)
    r = client.get("/admin/login/")
    assert css_url(site).encode() in r.content


@pytest.mark.django_db
def test_user_preference_beats_site_default(staff_client, staff_user):
    Theme.objects.create(name="Site", is_site_default=True)
    mine = Theme.objects.create(name="Mine", owner=staff_user)
    UserThemePreference.objects.create(user=staff_user, theme=mine)
    r = staff_client.get("/admin/")
    assert css_url(mine).encode() in r.content


@pytest.mark.django_db
def test_my_theme_choose_and_reset(staff_client, staff_user, shared_theme):
    url = reverse("grappelli_theme_editor:my-theme")
    assert staff_client.get(url).status_code == 200
    staff_client.post(url, {"action": "choose", "theme": shared_theme.pk})
    assert staff_user.grappelli_theme_preference.theme == shared_theme
    staff_client.post(url, {"action": "choose", "theme": ""})
    staff_user.grappelli_theme_preference.refresh_from_db()
    assert staff_user.grappelli_theme_preference.theme is None


@pytest.mark.django_db
def test_my_theme_cannot_pick_someone_elses_private_theme(
    staff_client, django_user_model
):
    other = django_user_model.objects.create_user("other", is_staff=True)
    theirs = Theme.objects.create(name="Theirs", owner=other)
    r = staff_client.post(
        reverse("grappelli_theme_editor:my-theme"),
        {"action": "choose", "theme": theirs.pk},
    )
    assert r.status_code == 404


@pytest.mark.django_db
def test_duplicate_creates_private_copy(staff_client, staff_user, shared_theme):
    r = staff_client.post(
        reverse("grappelli_theme_editor:my-theme"),
        {"action": "duplicate", "theme": shared_theme.pk},
    )
    copy = Theme.objects.get(owner=staff_user)
    assert r.status_code == 302
    assert r["Location"].endswith(f"/{copy.pk}/change/")
    assert copy.seeds == shared_theme.seeds


def _preview(client, data, theme=None):
    url = reverse("grappelli_theme_editor:preview-css")
    if theme:
        url += f"?theme={theme.pk}"
    base = {
        "name": "x",
        "color_scheme": "user",
        "seeds": json.dumps({"light": {}, "dark": {}}),
        "light_tokens": "{}",
        "dark_tokens": "{}",
        "components": "{}",
        "font_scale": "1",
        "radius_scale": "1",
        "spacing_scale": "1",
    }
    base.update(data)
    return client.post(url, base).json()


@pytest.mark.django_db
def test_preview_css_renders_unsaved_state(staff_client):
    data = _preview(
        staff_client,
        {
            "seeds": json.dumps({"light": {"accent": "#ff0000"}}),
            "components": json.dumps({"buttons": {"radius": 14}}),
        },
    )
    assert data["ok"]
    assert "--grp-link-color:#ff0000" in data["css"]
    assert "border-radius:14px !important" in data["css"]
    assert data["tokens"]["light"]["--grp-link-color"] == "#ff0000"
    assert not Theme.objects.exists()


@pytest.mark.django_db
def test_preview_css_reports_errors(staff_client):
    data = _preview(
        staff_client, {"components": json.dumps({"buttons": {"radius": 999}})}
    )
    assert not data["ok"]
    assert "components" in data["errors"]


@pytest.mark.django_db
def test_preview_css_reports_contrast(staff_client):
    data = _preview(
        staff_client,
        {"seeds": json.dumps({"light": {"text": "#ffffff"}})},
    )
    assert any(w["label"] == "Body text" for w in data["contrast"])


@pytest.mark.django_db
def test_preview_ignores_custom_css_from_non_superuser(staff_client):
    data = _preview(staff_client, {"custom_css": "body{display:none}"})
    assert "display:none" not in data["css"]


@pytest.mark.django_db
def test_preview_requires_edit_rights_on_existing_theme(staff_client, shared_theme):
    url = reverse("grappelli_theme_editor:preview-css") + f"?theme={shared_theme.pk}"
    assert staff_client.post(url, {"name": "x"}).status_code == 403


@pytest.mark.django_db
def test_preview_page_renders_without_active_theme(admin_client):
    Theme.objects.create(name="Site", is_site_default=True)
    r = admin_client.get(reverse("grappelli_theme_editor:preview"))
    assert r.status_code == 200
    assert b"data-grappelli-theme" not in r.content
    assert b"grp-pulldown-container" in r.content


@pytest.mark.django_db
def test_preview_inlines_unsaved_image(staff_client):
    from django.core.files.uploadedfile import SimpleUploadedFile

    url = reverse("grappelli_theme_editor:preview-css")
    data = {
        "name": "x",
        "color_scheme": "user",
        "seeds": "{}",
        "light_tokens": "{}",
        "dark_tokens": "{}",
        "components": json.dumps({"general": {"page_image": "tile"}}),
        "font_scale": "1",
        "radius_scale": "1",
        "spacing_scale": "1",
        "image": SimpleUploadedFile(
            "tile.png",
            b"\x89PNG\r\n\x1a\n" + b"0" * 20,
            content_type='image/png"); x:url(evil',
        ),
    }
    body = staff_client.post(url, data).json()
    assert body["ok"], body
    assert 'url("data:image/png;base64,' in body["css"]
    assert "evil" not in body["css"]


@pytest.mark.django_db
def test_fake_image_is_rejected(staff_client):
    from django.core.files.uploadedfile import SimpleUploadedFile

    url = reverse("grappelli_theme_editor:preview-css")
    body = staff_client.post(
        url,
        {
            "name": "x",
            "color_scheme": "user",
            "font_scale": "1",
            "radius_scale": "1",
            "spacing_scale": "1",
            "image": SimpleUploadedFile("evil.png", b"<html><script>x</script>"),
        },
    ).json()
    assert not body["ok"]
    assert "image" in body["errors"]


@pytest.mark.django_db
def test_only_superusers_add_web_fonts(staff_client, admin_client, staff_user):
    from django.contrib.auth.models import Permission

    staff_user.user_permissions.add(Permission.objects.get(codename="add_themefont"))
    url = reverse("grappelli_theme_editor:add-web-font")
    data = {"family": "Inter", "stylesheet_url": "https://evil.example/x.css"}
    assert staff_client.post(url, data).status_code == 403
    assert admin_client.post(url, data).json()["ok"]


@pytest.mark.django_db
def test_css_version_follows_rendered_bytes(shared_theme):
    from grappelli_theme_editor.models import ThemeFont

    shared_theme.font_sans = '"Brand", sans-serif'
    shared_theme.save()
    before = shared_theme.version_hash()
    ThemeFont.objects.create(family="Brand", stylesheet_url="https://x.example/b.css")
    assert shared_theme.version_hash() != before


@pytest.mark.django_db
def test_try_for_this_session(staff_client, staff_user, shared_theme):
    site = Theme.objects.create(name="Site", is_site_default=True)
    try_url = reverse("grappelli_theme_editor:try", args=[shared_theme.pk])
    r = staff_client.post(try_url, {"next": "https://evil.example/"})
    assert r.status_code == 302
    assert "evil" not in r["Location"]  # open redirect blocked
    assert css_url(shared_theme).encode() in staff_client.get("/admin/").content
    assert not UserThemePreference.objects.filter(user=staff_user).exists()
    staff_client.post(reverse("grappelli_theme_editor:stop-trying"))
    assert css_url(site).encode() in staff_client.get("/admin/").content


@pytest.mark.django_db
def test_cannot_try_someone_elses_private_theme(staff_client, django_user_model):
    other = django_user_model.objects.create_user("o", is_staff=True)
    theirs = Theme.objects.create(name="Theirs", owner=other)
    r = staff_client.post(reverse("grappelli_theme_editor:try", args=[theirs.pk]))
    assert r.status_code == 404


@pytest.mark.django_db
def test_stale_trial_is_dropped(staff_client, shared_theme, django_user_model):
    staff_client.post(reverse("grappelli_theme_editor:try", args=[shared_theme.pk]))
    other = django_user_model.objects.create_user("o", is_staff=True)
    shared_theme.owner = other
    shared_theme.name = "Secret name"
    shared_theme.save()
    page = staff_client.get(reverse("grappelli_theme_editor:my-theme")).content
    assert b"Secret name" not in page
    assert b"Appearance (trying)" not in page
