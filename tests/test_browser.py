"""End-to-end check of the editor's live preview (run with ``-m playwright``)."""

import os

import pytest

from grappelli_theme_editor.models import Theme

pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@pytest.fixture
def logged_in_page(page, live_server, django_user_model):
    django_user_model.objects.create_superuser("admin", "a@example.com", "admin")
    page.goto(f"{live_server.url}/admin/login/")
    page.fill("#id_username", "admin")
    page.fill("#id_password", "admin")
    page.click("input[type=submit]")
    return page


def test_live_preview_updates_without_saving(logged_in_page, live_server):
    page = logged_in_page
    theme = Theme.objects.create(name="Live")
    page.goto(
        f"{live_server.url}/admin/grappelli_theme_editor/theme/{theme.pk}/change/"
    )
    frame = page.frame_locator(".gte-frame")
    button = frame.locator(".gte-preview-buttons a.grp-button").first
    button.wait_for()

    page.click("button[data-tab=components]")
    radius = page.locator("input[data-comp=buttons][data-prop=radius][data-role=value]")
    radius.fill("17")
    radius.dispatch_event("input")
    page.wait_for_function(
        """() => {
            const doc = document.querySelector('.gte-frame').contentDocument;
            const b = doc.querySelector('.gte-preview-buttons a.grp-button');
            return getComputedStyle(b).borderTopLeftRadius === '17px';
        }""",
        timeout=10000,
    )

    page.click("button[data-tab=colors]")
    accent = page.locator(
        ".gte-color[data-kind=seed][data-key=accent][data-mode=light] "
        "input[data-role=value]"
    )
    accent.fill("#ff0000")
    page.wait_for_function(
        """() => {
            const doc = document.querySelector('.gte-frame').contentDocument;
            return getComputedStyle(doc.documentElement)
                .getPropertyValue('--grp-link-color').trim() === '#ff0000';
        }""",
        timeout=10000,
    )
    theme.refresh_from_db()
    assert theme.seeds == {"light": {}, "dark": {}}  # nothing saved yet

    page.click("input[name=_continue]")
    page.wait_for_load_state()
    theme.refresh_from_db()
    assert theme.seeds["light"] == {"accent": "#ff0000"}
    assert theme.components == {"buttons": {"radius": 17}}


def test_inspector_highlights_where_to_change_an_element(logged_in_page, live_server):
    page = logged_in_page
    theme = Theme.objects.create(name="Inspect")
    page.goto(
        f"{live_server.url}/admin/grappelli_theme_editor/theme/{theme.pk}/change/"
    )
    frame = page.frame_locator(".gte-frame")
    title = frame.locator("#grp-navigation h1#grp-admin-title")
    title.wait_for()
    page.wait_for_function(
        "() => document.querySelector('.gte-frame').contentDocument"
        ".getElementById('gte-live').textContent.length > 0"
    )
    title.dispatch_event("click")

    inspector = page.locator("[data-inspector]")
    inspector.wait_for(state="visible")
    assert "h1#grp-admin-title" in inspector.inner_text()
    # the bar's component section and the chrome seed are highlighted
    assert page.locator('details[data-comp-section="navbar"].gte-hit').count() == 1
    assert page.locator('tr[data-seed-row="chrome"].gte-hit').count() == 1
    assert (
        page.locator('tr[data-token-row="--grp-dark-background-color"].gte-hit').count()
        == 1
    )
    # clicking in inspect mode must not navigate the preview
    assert page.frames[1].url.endswith("/preview/")


def test_sections_collapse_and_remember_state(logged_in_page, live_server):
    page = logged_in_page
    theme = Theme.objects.create(name="Sections")
    url = f"{live_server.url}/admin/grappelli_theme_editor/theme/{theme.pk}/change/"
    page.goto(url)
    page.click("button[data-tab=components]")
    opened = page.locator("details[data-comp-section][open]")
    assert sorted(
        opened.evaluate_all("els => els.map(e => e.dataset.compSection)")
    ) == ["buttons", "footer", "icons", "navbar"]
    page.locator('details[data-comp-section="navbar"] > summary').click()
    page.reload()
    page.click("button[data-tab=components]")
    assert page.locator('details[data-comp-section="navbar"][open]').count() == 0


def test_take_colours_and_font_picker(logged_in_page, live_server):
    page = logged_in_page
    Theme.objects.create(
        name="Source",
        seeds={"light": {"accent": "#ff00ff"}, "dark": {}},
        components={
            "buttons": {"radius": 20},
            "navbar": {"text": {"light": "#123456"}},
        },
    )
    theme = Theme.objects.create(name="Target", components={"buttons": {"height": 40}})
    page.goto(
        f"{live_server.url}/admin/grappelli_theme_editor/theme/{theme.pk}/change/"
    )
    page.click("button[data-tab=load]")
    page.select_option("[data-take-source]", label="Source")
    page.click("button[data-take-part=colors]")
    seeds = page.locator("#id_seeds").input_value()
    components = page.locator("#id_components").input_value()
    assert "#ff00ff" in seeds
    assert '"height":40' in components  # shapes kept
    assert '"radius":20' not in components  # source shapes not taken
    assert "#123456" in components  # source colour props taken

    page.click("button[data-tab=typography]")
    assert page.locator("[data-typography-slot] #id_font_sans").count() == 1
    before = page.locator("#id_font_sans").input_value()
    # the menu opened next to "labels font" sets that field, nothing else
    page.locator("#id_font_label + .gte-font-open").click()
    menu = page.locator(".gte-font-menu")
    menu.wait_for(state="visible")
    menu.locator(".gte-font-group-web .gte-font-item", has_text="Lora").first.click()
    assert "Lora" in page.locator("#id_font_label").input_value()
    assert page.locator("#id_font_sans").input_value() == before
    assert page.locator("#id_web_font_provider").input_value() == "bunny"
    warning = page.locator("[data-webfont-warning]")
    assert warning.is_visible()
    assert "fonts.bunny.net" in warning.inner_text()


def test_icons_tab_and_emoji_picker(logged_in_page, live_server):
    page = logged_in_page
    theme = Theme.objects.create(name="Icons")
    page.goto(
        f"{live_server.url}/admin/grappelli_theme_editor/theme/{theme.pk}/change/"
    )
    page.click("button[data-tab=icons]")
    row = page.locator('tr[data-prop-row="icons.add_glyph"]')
    row.locator(".gte-emoji-open").click()
    page.locator(".gte-emoji-menu .gte-emoji", has_text="🚀").click()
    assert row.locator("input[data-type=glyph]").input_value() == "🚀"
    assert (
        page.locator("select[data-comp=icons][data-prop=add_icon]").input_value()
        == "custom"
    )
    page.wait_for_function(
        "() => document.querySelector('.gte-frame').contentDocument"
        ".getElementById('gte-live').textContent.includes('\\\\1f680')"
    )
    page.click("input[name=_continue]")
    page.wait_for_load_state()
    theme.refresh_from_db()
    assert theme.components["icons"] == {"add_icon": "custom", "add_glyph": "🚀"}
