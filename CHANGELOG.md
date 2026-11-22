# Changelog

## 0.1.0 (unreleased)

First release.

- Theme editor in the admin change form with a live preview (component
  catalogue or any admin page, light and dark).
- Preview inspector: click an element to see and jump to the base colours,
  component settings and colour tokens that style it.
- 7 base colours with derived palettes, every `--grp-*` token editable,
  light/dark aware, WCAG contrast warnings.
- 15 component groups (top bar, breadcrumbs, buttons, fields, modules,
  filters, tables and their empty-area pattern, messages, object tools,
  submit bar, pagination, login, pop-ups, icons & labels), global scales for
  font size, rounding and density.
- Fonts per role (interface, headings, labels, fields, monospace) from a menu
  with system fonts, uploaded fonts, Bunny Fonts / Google Fonts and fonts
  installed locally; any web font by stylesheet URL.
- Icons: replace or hide the Add icon, search magnifier and filter arrow; icons
  on the save/delete buttons (icon + text or icon only).
- Background image upload (tile, stretch, fit, corners).
- Site default plus a personal theme for every staff member ("Appearance"),
  private themes, "Load from…" another theme's colours/shapes/fonts, JSON
  import/export, twelve presets (`load_theme_presets`).
- "Make site default" buttons, "Try for this session".
- Bottom submit bar: floating (Grappelli), glued to the edge, macOS-like dock,
  or at the end of the form.
- Icons tab with an emoji picker, built-in outline icons and image URLs.
- Optional django-reversion support: history with live preview of old
  versions, revert, recover deleted themes.
- Translations: English, Polish, German, French, Spanish.
