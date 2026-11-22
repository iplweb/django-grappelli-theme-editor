# CLAUDE.md

`django-grappelli-theme-editor` — a Django app (PyPI package) that lets admins
theme the django-grappelli admin from the admin itself. Read `README.md`
("How it works") first.

## Language

Code, comments, docstrings, README and commit messages in **English** (PyPI
package). UI strings go through gettext; keep `locale/pl` complete
(`make messages`, translate, `make compilemessages`; commit the `.mo`).

## Layout

- `src/grappelli_theme_editor/` — the package (only this ships).
- `scripts/extract_tokens.py` — regenerates `tokens_data.py` from the
  installed Grappelli's `screen.css`. Never edit `tokens_data.py` by hand.
- `tests/` — pytest (functions, no TestCase). Postgres via testcontainers;
  `GTE_TEST_SQLITE=1` for SQLite. Browser tests are marked `playwright` and
  excluded by default (`-m playwright` to run).
- `example_project/` — demo site (`demo` app with publications/authors).

## Rules of thumb

- The live preview posts the form to `preview/css/` and the server renders
  CSS with `css.render_theme_css` — do not reimplement colour or CSS logic
  in JavaScript.
- Everything non-superusers type ends up in CSS: add new inputs to the
  whitelist validators (`validators.py`, `components.Prop.clean`).
- New component props: add them to `components.COMPONENTS` with Grappelli's
  default as `default` (values equal to the default are not stored).
- The layer in `css.py` replays *all* declarations of a property in source
  order; keep it that way or the cascade changes.
- Grappelli quirks: `button` is styled as a 25px icon button,
  `section{display:block}` beats `[hidden]`, `.grp-change-form .grp-module`
  has `min-width:960px`, and `grappelli.cleanInputTypes()` turns
  color/range/number inputs into text (disabled in the theme change form).
- Components with rules that depend on several props (icons, table empty-area
  pattern, page background image) use `Component.extra_rules(values,
  component, context)`; `context["image_url"]` is the uploaded image or, in
  the preview, a data: URI of the unsaved upload.
- Declarations are split with `css.split_declarations` (quote/bracket aware —
  data: URIs contain `;`). Never `.split(";")`.
- Web fonts: curated families in `webfonts.py`, provider per theme
  (`Theme.web_font_provider`, Bunny first); other web fonts are `ThemeFont`
  rows with `stylesheet_url`. Keep the privacy warnings when touching this.
- Translations: en (source), pl, de, fr, es. After changing strings run
  `make messages`, translate all four catalogs, `make compilemessages`.
- Before a release: adversarial review (Codex), then docs/PUBLISHING.md.
- No catch-all exception handlers.
