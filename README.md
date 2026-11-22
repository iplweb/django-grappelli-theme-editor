# django-grappelli-theme-editor

**Re-skin the [django-grappelli](https://github.com/sehmaschine/django-grappelli)
admin from inside the admin: colours, fonts, shapes, shadows, bars, icons,
even the stripes next to your tables, with a live preview and an inspector
that tells you what to change.**

[![CI](https://github.com/iplweb/django-grappelli-theme-editor/actions/workflows/ci.yml/badge.svg)](https://github.com/iplweb/django-grappelli-theme-editor/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/django-grappelli-theme-editor.svg)](https://pypi.org/project/django-grappelli-theme-editor/)
[![Python](https://img.shields.io/pypi/pyversions/django-grappelli-theme-editor.svg)](https://pypi.org/project/django-grappelli-theme-editor/)

## The inspector: click anything, see what styles it

Switch on **🎯 Inspect** above the live preview and click any element: the
top bar, a button, a table header. The editor reads the preview's own
stylesheets, works out which colours and settings actually style that element
(text, background, borders, shadows), switches to the right tab and makes the
matching base colours, component sections and colour tokens blink. The chips
above the preview take you straight to each of them.

![The inspector: clicking the site title highlights the top bar section, the text and bar base colours, and the exact colour tokens](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/inspector.png)

![Clicking a Delete button: Buttons section, base colours and the button's colour tokens](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/inspector-button.png)

## Before / after

| Stock Grappelli | Same page, “Dockside” theme |
|---|---|
| ![Stock Grappelli](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/before.png) | ![Dockside](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/after.png) |

**Dockside** turns the submit bar into a floating, centred dock with
background-less icon buttons, macOS style:

![The Dockside dock with outline icons](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/dock.png)

…or with colourful emoji (**Dockside Emoji**):

![The Dockside dock with emoji](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/dock-emoji.png)

## Seventeen ready-made themes

`python manage.py load_theme_presets` installs them. Several of them make
Grappelli stop looking like Grappelli.

| | | |
|---|---|---|
| **Dockside**<br>![](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/themes/dockside.png) | **Dockside Night**<br>![](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/themes/dockside-night.png) | **Dockside Emoji**<br>![](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/themes/dockside-emoji.png) |
| **Clean Slate**<br>![](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/themes/clean-slate.png) | **Material**<br>![](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/themes/material.png) | **Fluent**<br>![](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/themes/fluent.png) |
| **Terminal**<br>![](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/themes/terminal.png) | **Brutalist**<br>![](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/themes/brutalist.png) | **Nord**<br>![](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/themes/nord.png) |
| **Sakura**<br>![](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/themes/sakura.png) | **Solarized**<br>![](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/themes/solarized.png) | **Graphite**<br>![](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/themes/graphite.png) |
| **Midnight**<br>![](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/themes/midnight.png) | **Ocean**<br>![](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/themes/ocean.png) | **Warm paper**<br>![](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/themes/warm-paper.png) |
| **Forest**<br>![](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/themes/forest.png) | **High contrast**<br>![](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/themes/high-contrast.png) |  |

All presets pass the built-in WCAG contrast checks.

## What you can change

* **Colours.** 7 base colours (accent, page background, text, header/footer
  bar, errors, success, warning) for light *and* dark mode; the ~200 Grappelli
  colours are derived from them. Every single `--grp-*` token can also be set
  by hand. A theme can follow Grappelli's light/dark toggle or pin one mode.
* **Shapes & bars.** 14 groups: general, top bar, breadcrumbs, buttons, form
  fields, modules, filters & search, tables (including the striped empty area
  next to them: plain, stripes in either direction, dots, grid or your own
  image), messages, object tools, the bottom submit bar, pagination, login
  page and pop-ups. Each has rounding, heights, paddings, shadows, flat vs.
  gradient fills, lettering and colours.
* **Icons** (own tab). Swap or hide the “Add” icon, the search magnifier and
  the filter arrow, and put icons on Save / Save and continue / Save and add
  another / Delete, as *icon + text* or *icon only*. Pick from ~150 emoji in a
  picker, use the built-in outline icons (white or dark), or give each button
  your own image URL. Buttons can be filled or background-less, at any icon
  size. No floppy disk by default: “Save” is a check mark, with a cloud, a
  tray or (for nostalgics) the floppy as alternatives.

  ![Save icon choices](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/save-icons.png)
* **The bottom submit bar.** Keep Grappelli's floating bar, glue it to the
  bottom edge, turn it into a centred **dock** that is only as wide as its
  buttons (like the macOS dock, at the height you like, with a floating
  shadow), or let it sit at the end of the form.
* **Typography.** Interface, headings, labels, form fields and monospace
  fonts, picked from a menu with safe system fonts, your uploaded fonts, web
  fonts (Bunny Fonts or Google Fonts) and the fonts installed on your computer.
  Global scales for font size, corner rounding and density.
* **Background image.** Upload a small picture and tile it, stretch it, fit
  it or pin it to a corner, scrolling or fixed.
* **Load from…** Copy only the colours, only the shapes or only the fonts of
  another theme into the one you are editing.

![Icons tab with the emoji picker](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/icons.png)

![Shapes & bars, with change counters on every section](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/editor-shapes.png)

![The font menu: web fonts are marked and say where they would be downloaded from](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/font-menu.png)

Everyone gets an **Appearance** page (link in the user menu) to pick a theme
for themselves, or to customise a private copy:

![The Appearance page](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/appearance.png)

## Trying and switching themes

* **★ Make site default.** A button next to every shared theme in the list and
  on the theme's page; it moves the default from the previous theme.
* **👁 Try for this session.** Look at a saved theme in your browser session
  only, without changing your saved choice or anybody else's admin. *Stop
  trying* returns to normal.

![The theme list with “Make site default” buttons](https://raw.githubusercontent.com/iplweb/django-grappelli-theme-editor/main/docs/screenshots/themes-list.png)

## Undo with django-reversion

With [django-reversion](https://github.com/etianen/django-reversion) in
`INSTALLED_APPS` (`pip install django-grappelli-theme-editor[reversion]`), the
theme admin becomes a `VersionAdmin`. Every save, “Make site default” and
copy is recorded, *History* lists the versions, and opening an old version
shows it in the editor **with the live preview**, so you can see what you are
going back to before pressing Save. Theme managers can also recover deleted
themes. Without reversion nothing changes.

## Installation

Requires Python ≥ 3.11, Django ≥ 5.2 and django-grappelli 5.x. Grappelli 4
has no CSS custom properties to theme.

```bash
pip install django-grappelli-theme-editor
```

```python
INSTALLED_APPS = [
    "grappelli_theme_editor",  # BEFORE grappelli, see "Templates"
    "grappelli",
    "django.contrib.admin",
    # ...
]

TEMPLATES = [{
    # ...
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",  # required
        # ...
    ]},
}]
```

```python
# urls.py
urlpatterns = [
    path("grappelli/", include("grappelli.urls")),
    path("admin/themes/", include("grappelli_theme_editor.urls")),
    path("admin/", admin.site.urls),
]
```

```bash
python manage.py migrate
python manage.py load_theme_presets   # optional: the seventeen themes above
```

Uploaded fonts and background images are `FileField`s, so `MEDIA_URL` and
`MEDIA_ROOT` must be served.

### Templates

The app ships an `admin/base_site.html` that extends the *next*
`admin/base_site.html` in the loader chain (Grappelli's) and adds the theme
stylesheet plus the **Appearance** link. That is why it must come before
`grappelli`. If your project has its own `admin/base_site.html` in
`TEMPLATES["DIRS"]`, add the tags yourself:

```django
{% load grappelli_theme_editor %}
{% block extrastyle %}{{ block.super }}{% grappelli_theme_stylesheet %}{% endblock %}
{% block userlinks %}{{ block.super }}{% grappelli_theme_user_link %}{% endblock %}
```

The system check `grappelli_theme_editor.W002` warns when the order is wrong.

## Usage

* **Admin › Admin themes › Themes.** List, add, edit, duplicate, import and
  export (JSON) themes, and set the site default. The change form *is* the
  editor: tabs *Colours*, *Shapes & bars*, *Icons*, *Typography*, *All colour
  tokens* and *Load from…*, with the live preview (light/dark) on the right.
  Nothing is saved until you press Save.
* **Appearance** (`/admin/themes/me/`). Each staff member picks a theme for
  themselves or “Site default”.
* **Admin › Admin themes › Fonts.** Upload `woff2`/`woff`/`ttf`/`otf` files or
  register any web font stylesheet URL (Adobe Fonts kit, Fontsource on
  jsDelivr, a company CDN…). You can also add web fonts straight from the
  font menu.

Which theme is shown: the one being tried in this session, else the user's
own choice, else the site default, else plain Grappelli. The login page uses
the site default.

### Web fonts and privacy

Picking a web font makes every admin user's browser download it from a third
party. The editor marks web fonts, names the server and shows a warning while
one is in use.

* **Bunny Fonts** (`fonts.bunny.net`, the default) is an EU-hosted drop-in
  for the Google Fonts API that, according to bunny.net, does not log IP
  addresses.
* **Google Fonts** sends the users' IP addresses to Google. In the EU this
  may require consent under the GDPR.
* **Uploaded font files** are self-hosted and contact nobody.

Previews of web fonts in the menu load only when you click *Show previews*.
Set `ALLOW_WEB_FONTS: False` to switch web fonts off entirely.

### Permissions

* Users with the model permissions (`change_theme` …) manage all themes, set
  the site default and recover deleted themes.
* Other staff members (when `ALLOW_USER_THEMES` is on) see shared themes
  read-only and fully manage their own private themes, which nobody else can
  see.
* **Custom CSS** is appended verbatim, so only superusers can edit it, and
  only superusers can register web fonts by stylesheet URL (a remote
  stylesheet is as powerful as custom CSS). Uploaded images and fonts are
  checked by their file signature, not just the extension.
  Everything else is validated against whitelists (colours, font family
  names, URLs, icon characters, numbers in range, known option keys) and
  escaped, so a theme cannot inject arbitrary CSS.

## Settings

```python
GRAPPELLI_THEME_EDITOR = {
    "ALLOW_USER_THEMES": True,            # staff may build private themes
    "ALLOW_WEB_FONTS": True,              # web fonts in themes and the font menu
    "WEB_FONT_PROVIDERS": ["bunny", "google"],  # offered, in this order
    "CACHE_TIMEOUT": 86400,               # seconds rendered CSS stays cached
    "USER_TOOLS_LINK": True,              # "Appearance" link in the user menu
    "MAX_FONT_SIZE": 2 * 1024 * 1024,     # bytes
    "MAX_IMAGE_SIZE": 512 * 1024,         # bytes
}
```

## Translations

English, Polish, German, French and Spanish. Grappelli itself relies on
Django's admin translations, so the rest of the admin is translated too.

## How it works

No Sass and no build step. Grappelli 5 exposes its palette as about 200 CSS
custom properties for light and dark mode. A theme is a small generated
stylesheet loaded after Grappelli's:

1. `@import` rules for the web fonts it uses and `@font-face` rules for
   uploaded fonts;
2. a *layer* that re-declares Grappelli's hardcoded font families, font sizes,
   radii and paddings as `calc(<original> * var(--gte-…-scale, 1))`. It
   replays *all* declarations of each property in Grappelli's source order,
   so the cascade is unchanged, and only the parts a theme uses are emitted;
3. the theme's `--grp-*` / `--gte-*` values under Grappelli's own selectors
   (`:root`, `html[data-theme=dark]`, `prefers-color-scheme` with `auto`);
4. component rules and per-element fonts (`!important`, because some of the
   Grappelli rules they replace are too), then the custom CSS.

The live preview posts the unsaved form to the server, which renders the CSS
with the same Python code that serves saved themes. Stylesheet URLs are
versioned (`/theme/<pk>/<hash>.css`) and served with `immutable` caching and
an ETag.

| Piece | Where |
|---|---|
| Grappelli's tokens and hardcoded declarations (generated) | `tokens_data.py`, via `scripts/extract_tokens.py` |
| Token groups and palette families | `tokens.py` |
| Base colours → all tokens | `palette.py` |
| Components, icons, patterns, background image | `components.py` |
| Stylesheet generation | `css.py` |
| Curated web fonts and providers | `webfonts.py` |
| Contrast checks | `contrast.py` |

**Upgrading Grappelli:** `tests/test_tokens.py` fails when the installed
Grappelli CSS no longer matches `tokens_data.py`. Run `make tokens`, review the
diff and check the selectors in `components.py`.

## Development

```bash
uv sync                                  # dev, test and example extras
uv run pytest                            # Postgres via testcontainers (Docker)
GTE_TEST_SQLITE=1 uv run pytest          # without Docker
uv run playwright install chromium       # once
uv run pytest -m playwright              # browser tests (preview, inspector…)
make demo                                # example project on :8000
```

Translations: `make messages`, edit `locale/*/LC_MESSAGES/django.po`, then
`make compilemessages`.

## Thanks

To Patrick Kranzlmüller and everyone who has worked on Grappelli over the
years: this package only exists because Grappelli is such a solid base to
build on.

## License

MIT
