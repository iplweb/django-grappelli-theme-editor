/*
 * Theme editor for django-grappelli-theme-editor.
 *
 * The controls are plain inputs rendered by the server. This script
 *  - mirrors them into the hidden JSON fields the model form saves
 *    (seeds, light_tokens, dark_tokens, components),
 *  - posts the whole form to the preview endpoint (debounced); the server
 *    renders the CSS with the same Python code used for saved themes, so
 *    there is no client-side colour maths to keep in sync,
 *  - injects that CSS into the preview iframe, which can show the component
 *    catalogue or any other admin page.
 */
(function () {
  "use strict";

  var editor = document.getElementById("gte-editor");
  if (!editor || !document.getElementById("id_seeds")) return;
  var form = editor.closest("form");
  var frame = editor.querySelector(".gte-frame");
  var statusEl = editor.querySelector("[data-status]");
  var warningsEl = editor.querySelector("[data-warnings]");
  var previewCssUrl = editor.dataset.previewCssUrl;
  var previewMode = "light";
  var lastCss = null;
  var lastTokens = { light: {}, dark: {} };

  var hidden = {
    seeds: document.getElementById("id_seeds"),
    light: document.getElementById("id_light_tokens"),
    dark: document.getElementById("id_dark_tokens"),
    components: document.getElementById("id_components"),
  };

  function readJSON(input, fallback) {
    if (!input || !input.value) return fallback;
    try {
      var value = JSON.parse(input.value);
      return value && typeof value === "object" ? value : fallback;
    } catch (e) {
      console.warn("theme editor: invalid JSON in", input.id, e);
      return fallback;
    }
  }

  // ---------------------------------------------------------------- colours

  function normalizeHex(value) {
    var v = (value || "").trim().toLowerCase();
    if (/^#[0-9a-f]{3}$/.test(v)) {
      return "#" + v[1] + v[1] + v[2] + v[2] + v[3] + v[3];
    }
    if (/^#[0-9a-f]{6}$/.test(v)) return v;
    if (/^#[0-9a-f]{8}$/.test(v)) return v.slice(0, 7);
    if (v === "white") return "#ffffff";
    if (v === "black") return "#000000";
    return null;
  }

  function colorWidgets() {
    return editor.querySelectorAll(".gte-color");
  }

  function setupColor(widget) {
    var text = widget.querySelector("[data-role=value]");
    var picker = widget.querySelector("[data-role=picker]");
    var syncPicker = function () {
      var hasValue = text.value.trim() !== "";
      var fallback = normalizeHex(text.placeholder);
      var hex = normalizeHex(text.value) || fallback;
      if (hex) picker.value = hex;
      widget.classList.toggle("gte-set", hasValue);
      // Not set and no known default colour (e.g. component colours, which
      // keep Grappelli's own expression): show a crossed swatch, not white.
      widget.classList.toggle("gte-unknown-default", !hasValue && !fallback);
    };
    picker.addEventListener("input", function () {
      text.value = picker.value;
      syncPicker();
      changed();
    });
    text.addEventListener("input", function () {
      syncPicker();
      changed();
    });
    widget.querySelector("[data-reset]").addEventListener("click", function () {
      text.value = "";
      syncPicker();
      changed();
    });
    widget._sync = syncPicker;
  }

  // ------------------------------------------------------------- components

  function setupLength(wrapper) {
    var range = wrapper.querySelector("[data-role=range]");
    var number = wrapper.querySelector("[data-role=value]");
    var sync = function () {
      range.value = number.value === "" ? number.dataset.default : number.value;
      wrapper.classList.toggle("gte-set", number.value !== "");
    };
    range.addEventListener("input", function () {
      number.value = range.value;
      sync();
      changed();
    });
    number.addEventListener("input", function () {
      sync();
      changed();
    });
    wrapper.querySelector("[data-reset]").addEventListener("click", function () {
      number.value = "";
      sync();
      changed();
    });
    wrapper._sync = sync;
  }

  // ------------------------------------------------------- load / serialize

  function load() {
    var seeds = readJSON(hidden.seeds, {});
    var tokens = { light: readJSON(hidden.light, {}), dark: readJSON(hidden.dark, {}) };
    var components = readJSON(hidden.components, {});

    colorWidgets().forEach(function (w) {
      var d = w.dataset;
      var value;
      if (d.kind === "seed") value = (seeds[d.mode] || {})[d.key];
      else if (d.kind === "token") value = tokens[d.mode][d.key];
      else if (d.kind === "comp") value = ((components[d.key] || {})[d.prop] || {})[d.mode];
      w.querySelector("[data-role=value]").value = value || "";
      w._sync();
    });
    editor.querySelectorAll("[data-comp][data-role=value]").forEach(function (input) {
      var value = (components[input.dataset.comp] || {})[input.dataset.prop];
      if (input.tagName === "SELECT") {
        input.value = value === undefined ? input.dataset.default : value;
      } else {
        input.value = value === undefined ? "" : value;
        var length = input.closest(".gte-length");
        if (length) length._sync();
      }
    });
  }

  function serialize() {
    var seeds = { light: {}, dark: {} };
    var tokens = { light: {}, dark: {} };
    var components = {};
    var put = function (comp, prop, value) {
      (components[comp] = components[comp] || {})[prop] = value;
    };

    colorWidgets().forEach(function (w) {
      var d = w.dataset;
      var value = w.querySelector("[data-role=value]").value.trim();
      if (!value) return;
      if (d.kind === "seed") seeds[d.mode][d.key] = value;
      else if (d.kind === "token") tokens[d.mode][d.key] = value;
      else if (d.kind === "comp") {
        var current = (components[d.key] || {})[d.prop] || {};
        current[d.mode] = value;
        put(d.key, d.prop, current);
      }
    });
    editor.querySelectorAll("[data-comp][data-role=value]").forEach(function (input) {
      var value = input.value;
      if (value === "" || value === input.dataset.default) return;
      var keepText = input.tagName === "SELECT" ||
        input.dataset.type === "glyph" || input.dataset.type === "url";
      put(input.dataset.comp, input.dataset.prop, keepText ? value.trim() : parseInt(value, 10));
    });

    updateChangeCounts(seeds, tokens, components);

    hidden.seeds.value = JSON.stringify(seeds);
    hidden.light.value = JSON.stringify(tokens.light);
    hidden.dark.value = JSON.stringify(tokens.dark);
    hidden.components.value = JSON.stringify(components);
  }

  function setCount(badge, n) {
    if (!badge) return; // e.g. the "Load from…" tab has no counter
    badge.textContent = n ? String(n) : "";
    badge.hidden = !n;
  }

  // Number of changed settings per section and per tab.
  function updateChangeCounts(seeds, tokens, components) {
    var total = { colors: 0, components: 0, tokens: 0 };
    total.colors = Object.keys(seeds.light).length + Object.keys(seeds.dark).length;
    total.tokens = Object.keys(tokens.light).length + Object.keys(tokens.dark).length;
    total.icons = 0;
    editor.querySelectorAll("[data-comp-section]").forEach(function (section) {
      var key = section.dataset.compSection;
      var n = Object.keys(components[key] || {}).length;
      if (key === "icons") total.icons += n;
      else total.components += n;
      setCount(section.querySelector("[data-changed-count]"), n);
    });
    editor.querySelectorAll(".gte-token-group").forEach(function (group) {
      var n = 0;
      group.querySelectorAll('.gte-color[data-kind="token"] [data-role=value]')
        .forEach(function (input) { if (input.value.trim()) n++; });
      setCount(group.querySelector("[data-changed-count]"), n);
    });
    total.typography = 0;
    ["id_font_sans", "id_font_heading", "id_font_label", "id_font_field", "id_font_mono"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el && el.value.trim()) total.typography++;
    });
    ["id_font_scale", "id_radius_scale", "id_spacing_scale"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el && el.value !== "" && parseFloat(el.value.replace(",", ".")) !== 1) {
        total.typography++;
      }
    });
    editor.querySelectorAll(".gte-tab").forEach(function (tab) {
      setCount(tab.querySelector("[data-tab-count]"), total[tab.dataset.tab]);
    });
  }

  // ----------------------------------------------------------- live preview

  var timer = null;
  var inflight = null;

  function changed() {
    serialize();
    clearTimeout(timer);
    timer = setTimeout(refresh, 200);
  }

  function setStatus(text, isError) {
    statusEl.textContent = text;
    statusEl.classList.toggle("gte-status-error", !!isError);
  }

  function refresh() {
    if (inflight) inflight.abort();
    inflight = new AbortController();
    setStatus(gettext("updating", "Updating…"));
    fetch(previewCssUrl, {
      method: "POST",
      body: new FormData(form),
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      signal: inflight.signal,
    })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        if (!data.ok) {
          var msgs = [];
          Object.keys(data.errors).forEach(function (k) {
            msgs.push(k + ": " + data.errors[k].join(" "));
          });
          setStatus(msgs.join(" · "), true);
          return;
        }
        lastCss = data.css;
        lastTokens = data.tokens;
        applyToFrame();
        showEffectiveTokens();
        showWarnings(data.contrast);
        setStatus("");
      })
      .catch(function (err) {
        if (err.name === "AbortError") return;
        console.error("theme editor preview failed", err);
        setStatus(gettext("failed", "Preview failed: ") + err.message, true);
      });
  }

  function frameDoc() {
    try {
      return frame.contentDocument;
    } catch (e) {
      return null; // navigated to another origin
    }
  }

  function prepareFrame() {
    var doc = frameDoc();
    if (!doc || !doc.head) return;
    // Drop the viewer's own active theme; the editor's CSS replaces it.
    doc.querySelectorAll("link[data-grappelli-theme]").forEach(function (l) {
      l.remove();
    });
    if (!doc.getElementById("gte-live")) {
      var style = doc.createElement("style");
      style.id = "gte-live";
      doc.head.appendChild(style);
    }
    var header = doc.getElementById("grp-header");
    var win = frame.contentWindow;
    if (header && win.ResizeObserver && !header._gteObserved) {
      header._gteObserved = true;
      new win.ResizeObserver(function () {
        doc.documentElement.style.setProperty(
          "--gte-header-height",
          header.offsetHeight + "px"
        );
      }).observe(header);
    }
    clearInspection();
    installInspector(doc);
    applyToFrame();
  }

  function applyToFrame() {
    var doc = frameDoc();
    if (!doc) return;
    var style = doc.getElementById("gte-live");
    if (style && lastCss !== null) style.textContent = lastCss;
    doc.documentElement.dataset.theme = previewMode;
  }

  function showEffectiveTokens() {
    editor.querySelectorAll('.gte-color[data-kind="token"]').forEach(function (w) {
      var text = w.querySelector("[data-role=value]");
      var effective = lastTokens[w.dataset.mode][w.dataset.key];
      text.placeholder = effective && effective.indexOf("var(") !== 0
        ? effective
        : w.dataset.default;
      w.classList.toggle("gte-derived", !text.value && !!effective);
      w._sync();
    });
  }

  function showWarnings(list) {
    warningsEl.innerHTML = "";
    warningsEl.hidden = !list.length;
    list.forEach(function (w) {
      var li = document.createElement("li");
      li.textContent = interpolate(
        gettext("lowContrast", "Low contrast (%(mode)s): %(label)s — %(ratio)s:1, needs %(minimum)s:1"),
        {
          mode: gettext(w.mode, w.mode),
          label: w.label,
          ratio: w.ratio,
          minimum: w.minimum,
        }
      );
      warningsEl.appendChild(li);
    });
  }

  // ------------------------------------------------------------ typography

  // The font/scale model fields are rendered by Django as a normal fieldset;
  // move it into the editor's "Typography" tab.
  function setupTypography() {
    var slot = editor.querySelector("[data-typography-slot]");
    var field = document.getElementById("id_font_sans");
    var fieldset = field && field.closest("fieldset");
    if (slot && fieldset) slot.appendChild(fieldset);
    // The background image upload goes to the top of the "General" section,
    // next to the options that place it.
    var image = document.getElementById("id_image");
    var imageFieldset = image && image.closest("fieldset");
    var general = editor.querySelector('[data-comp-section="general"]');
    if (imageFieldset && general) {
      general.insertBefore(imageFieldset, general.querySelector("table"));
      image.addEventListener("change", changed);
    }
  }

  // ------------------------------------------------------------ font menu
  //
  // Every font field gets a "Choose…" button opening one shared drop-down:
  // system fonts, your fonts, web fonts per service (marked, with a warning
  // and previews only on request), fonts installed on this computer and a
  // small form to add any other web font by URL.

  var FONT_FIELDS = ["id_font_sans", "id_font_heading", "id_font_label", "id_font_field", "id_font_mono"];
  var fontDataEl = document.getElementById("gte-font-picker");
  var fontData = fontDataEl ? JSON.parse(fontDataEl.textContent) : null;
  var menu = null;
  var menuTarget = null;

  function familiesIn(value) {
    return (value || "").split(",").map(function (p) {
      return p.trim().replace(/^["']|["']$/g, "").toLowerCase();
    }).filter(Boolean);
  }

  function webFontHost(family) {
    // -> host the family would be downloaded from, or null (not a web font)
    if (!fontData) return null;
    var own = fontData.uploaded.find(function (f) {
      return f.web && f.family.toLowerCase() === family;
    });
    if (own) return new URL(own.url).host;
    if (fontData.uploaded.some(function (f) { return f.family.toLowerCase() === family; })) {
      return null; // uploaded file: self-hosted
    }
    var providerField = document.getElementById("id_web_font_provider");
    var key = providerField ? providerField.value : "bunny";
    var provider = fontData.web.find(function (p) { return p.key === key; });
    if (provider && provider.families.some(function (f) { return f.family.toLowerCase() === family; })) {
      return provider.host;
    }
    return null;
  }

  function updateWebfontWarning() {
    var warning = editor.querySelector("[data-webfont-warning]");
    if (!warning) return;
    var fonts = [], hosts = [];
    FONT_FIELDS.forEach(function (id) {
      var el = document.getElementById(id);
      if (!el) return;
      familiesIn(el.value).forEach(function (family) {
        var host = webFontHost(family);
        if (!host) return;
        if (fonts.indexOf(family) === -1) fonts.push(family);
        if (hosts.indexOf(host) === -1) hosts.push(host);
      });
    });
    warning.hidden = !fonts.length;
    if (!fonts.length) return;
    var text = interpolate(gettext("webInUse", "⚠ Web font in use"), {
      fonts: fonts.join(", "),
      hosts: hosts.join(", "),
    });
    if (hosts.some(function (h) { return h.indexOf("google") !== -1; })) {
      text += " " + gettext("googleNote", "");
    }
    warning.textContent = text;
  }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text) node.textContent = text;
    return node;
  }

  function fontItem(label, value, opts) {
    opts = opts || {};
    var b = el("button", "gte-font-item");
    b.type = "button";
    b.dataset.value = value;
    if (opts.provider) b.dataset.provider = opts.provider;
    var name = el("span", "gte-font-item-name", label);
    if (opts.sample !== false) name.style.fontFamily = value;
    b.appendChild(name);
    if (opts.web) b.appendChild(el("span", "gte-badge-web", gettext("webBadge", "web")));
    b.addEventListener("click", function () { pickFont(b); });
    return b;
  }

  function pickFont(item) {
    if (!menuTarget) return;
    menuTarget.value = item.dataset.value;
    if (item.dataset.provider) {
      var provider = document.getElementById("id_web_font_provider");
      if (provider) {
        provider.value = item.dataset.provider;
        provider.dispatchEvent(new Event("input", { bubbles: true }));
      }
    }
    menuTarget.dispatchEvent(new Event("input", { bubbles: true }));
    closeMenu();
  }

  function group(title, note) {
    var g = el("div", "gte-font-group");
    var h = el("div", "gte-font-group-title", title);
    g.appendChild(h);
    if (note) g.appendChild(el("div", "gte-font-group-note", note));
    return g;
  }

  function csrfToken() {
    var input = form.querySelector("input[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  function buildMenu() {
    menu = el("div", "gte-font-menu");
    menu.hidden = true;
    menu.setAttribute("role", "dialog");
    var search = el("input", "vTextField gte-font-search");
    search.type = "search";
    search.placeholder = gettext("filterFonts", "Search fonts…");
    menu.appendChild(search);
    var body = el("div", "gte-font-menu-body");
    menu.appendChild(body);

    var system = group(gettext("systemFonts", "Safe system fonts"));
    fontData.system.forEach(function (f) { system.appendChild(fontItem(f.label, f.value)); });
    body.appendChild(system);

    var yours = group(gettext("yourFonts", "Your fonts"));
    yours.dataset.group = "yours";
    var seen = {};
    fontData.uploaded.forEach(function (f) {
      if (seen[f.family]) return;
      seen[f.family] = true;
      yours.appendChild(fontItem(f.family, '"' + f.family + '", sans-serif', {
        web: f.web, sample: !f.web,
      }));
    });
    body.appendChild(yours);
    if (!fontData.uploaded.length) yours.hidden = true;

    fontData.web.forEach(function (provider) {
      var g = group(
        interpolate(gettext("webFonts", "Web fonts from %(name)s"), { name: provider.name }),
        interpolate(gettext("webWarning", "Downloads from %(host)s"), { host: provider.host })
      );
      g.classList.add("gte-font-group-web");
      var show = el("button", "gte-link-button gte-font-previews",
        interpolate(gettext("showPreviews", "Show previews"), { host: provider.host }));
      show.type = "button";
      show.addEventListener("click", function () {
        provider.families.forEach(function (f) {
          var link = document.createElement("link");
          link.rel = "stylesheet";
          link.href = f.url;
          document.head.appendChild(link);
        });
        g.querySelectorAll(".gte-font-item").forEach(function (item) {
          item.querySelector(".gte-font-item-name").style.fontFamily = item.dataset.value;
        });
        show.remove();
      });
      g.appendChild(show);
      provider.families.forEach(function (f) {
        g.appendChild(fontItem(f.family, f.value, { web: true, sample: false, provider: provider.key }));
      });
      body.appendChild(g);
    });

    var local = group(gettext("localFonts", "Fonts on this computer"));
    var detect = el("button", "gte-link-button", gettext("detectLocal", "Detect installed fonts"));
    detect.type = "button";
    var localStatus = el("div", "gte-font-group-note");
    detect.addEventListener("click", function () {
      if (typeof window.queryLocalFonts !== "function") {
        localStatus.textContent = gettext("noLocalFonts", "This browser cannot list installed fonts.");
        return;
      }
      window.queryLocalFonts().then(function (fonts) {
        var families = [];
        fonts.forEach(function (f) {
          if (families.indexOf(f.family) === -1) families.push(f.family);
        });
        families.sort(function (a, b) { return a.localeCompare(b); });
        families.forEach(function (family) {
          local.appendChild(fontItem(family, '"' + family + '", sans-serif'));
        });
        detect.remove();
        localStatus.textContent = "";
      }).catch(function (err) {
        if (err && (err.name === "NotAllowedError" || err.name === "SecurityError")) {
          localStatus.textContent = gettext("localDenied", "Permission denied.");
          return;
        }
        throw err;
      });
    });
    local.appendChild(detect);
    local.appendChild(localStatus);
    body.appendChild(local);

    if (fontData.canAddWebFont) {
      var add = group(gettext("addWebFont", "Add another web font by URL…"));
      var family = el("input", "vTextField");
      family.placeholder = gettext("family", "Family name");
      var url = el("input", "vTextField");
      url.placeholder = gettext("cssUrl", "Stylesheet URL");
      var submit = el("button", "gte-take-button", gettext("add", "Add"));
      submit.type = "button";
      var error = el("div", "gte-font-group-note gte-error");
      submit.addEventListener("click", function () {
        var data = new FormData();
        data.append("family", family.value);
        data.append("stylesheet_url", url.value);
        fetch(fontData.addWebFontUrl, {
          method: "POST",
          body: data,
          credentials: "same-origin",
          headers: { "X-CSRFToken": csrfToken() },
        }).then(function (r) {
          var type = r.headers.get("Content-Type") || "";
          if (type.indexOf("application/json") === -1) {
            throw new Error("HTTP " + r.status);
          }
          return r.json();
        }).then(function (result) {
          if (!result.ok) {
            error.textContent = Object.values(result.errors).join(" ");
            return;
          }
          fontData.uploaded.push({ family: result.family, web: true, url: result.url });
          var item = fontItem(result.family, '"' + result.family + '", sans-serif', {
            web: true, sample: false,
          });
          yours.hidden = false;
          yours.appendChild(item);
          pickFont(item);
        }).catch(function (err) {
          console.error("adding a web font failed", err);
          error.textContent = err.message;
        });
      });
      [family, url, submit, error].forEach(function (n) { add.appendChild(n); });
      body.appendChild(add);
    }

    search.addEventListener("input", function () {
      var q = search.value.trim().toLowerCase();
      body.querySelectorAll(".gte-font-item").forEach(function (item) {
        item.hidden = q && item.textContent.toLowerCase().indexOf(q) === -1;
      });
    });
    menu.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeMenu();
    });
    document.body.appendChild(menu);
    document.addEventListener("mousedown", function (e) {
      if (!menu.hidden && !menu.contains(e.target) && !e.target.closest(".gte-font-open")) {
        closeMenu();
      }
    });
  }

  function openMenu(input) {
    if (!menu) buildMenu();
    menuTarget = input;
    var rect = input.getBoundingClientRect();
    menu.style.left = (rect.left + window.scrollX) + "px";
    menu.style.top = (rect.bottom + window.scrollY + 4) + "px";
    menu.style.minWidth = Math.max(rect.width, 320) + "px";
    menu.hidden = false;
    var search = menu.querySelector(".gte-font-search");
    search.value = "";
    search.dispatchEvent(new Event("input"));
    search.focus();
  }

  function closeMenu() {
    if (menu) menu.hidden = true;
    if (menuTarget) menuTarget.focus();
    menuTarget = null;
  }

  function setupFontMenus() {
    if (!fontData) return;
    FONT_FIELDS.forEach(function (id) {
      var input = document.getElementById(id);
      if (!input) return;
      var button = el("button", "gte-take-button gte-font-open", gettext("choose", "Choose…"));
      button.type = "button";
      button.addEventListener("click", function () {
        if (menu && !menu.hidden && menuTarget === input) closeMenu();
        else openMenu(input);
      });
      input.insertAdjacentElement("afterend", button);
    });
  }

  // ------------------------------------------------------------ emoji menu

  var EMOJI = [
    ["Save", "💾 📀 💿 ✅ ✔️ ☑️ 📥 🗂️ 📁 📂 🗄️ 📦 🔒 👍"],
    ["Edit", "✏️ 📝 🖊️ 🖋️ ✍️ 🔧 🛠️ ⚙️ 🔁 🔄 ↩️ ↪️ ⏎ ✂️"],
    ["Add", "➕ ✚ ＋ 🆕 ✨ 🌟 ⭐ 📌 📎 🔖 🎁 🧩"],
    ["Delete", "🗑️ ❌ ✖️ ⛔ 🚫 💥 🔥 ⚠️ ❗ 🧹 💣 ☠️"],
    ["Search", "🔍 🔎 🧭 🗺️ 👀 👁️ 🔦 🧐"],
    ["Arrows", "▶️ ◀️ ⬆️ ⬇️ ➡️ ⬅️ ↗️ ↘️ ⏩ ⏪ ⏫ ⏬ ▾ ▴ › » → ⇢"],
    ["Office", "📄 📃 📑 📊 📈 📉 🗓️ 📅 ✉️ 📧 📨 📤 🖨️ 💼 📚 📖 🎓 🏛️ 🔬 🧪"],
    ["Fun", "🌸 🌻 🍀 🌈 ☀️ 🌙 ⚡ 🎉 🎈 🚀 🐱 🐶 🦄 🍕 ☕ 🎵 ❤️ 💜 💙 💚 🧡 🤖"],
    ["Symbols", "★ ☆ ● ○ ■ □ ◆ ◇ ✓ ✗ ♥ ♦ ♣ ♠ ∞ § ¶ † ⌘ ⌂ ☰ ⚑"],
  ];
  var emojiMenu = null;
  var emojiTarget = null;

  function closeEmojiMenu() {
    if (emojiMenu) emojiMenu.hidden = true;
    emojiTarget = null;
  }

  function buildEmojiMenu() {
    emojiMenu = el("div", "gte-font-menu gte-emoji-menu");
    emojiMenu.hidden = true;
    EMOJI.forEach(function (group) {
      var g = el("div", "gte-font-group");
      g.appendChild(el("div", "gte-font-group-title", group[0]));
      var grid = el("div", "gte-emoji-grid");
      group[1].split(" ").forEach(function (emoji) {
        var b = el("button", "gte-emoji", emoji);
        b.type = "button";
        b.addEventListener("click", function () {
          if (!emojiTarget) return;
          emojiTarget.value = emoji;
          emojiTarget.dispatchEvent(new Event("input", { bubbles: true }));
          closeEmojiMenu();
        });
        grid.appendChild(b);
      });
      g.appendChild(grid);
      emojiMenu.appendChild(g);
    });
    emojiMenu.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeEmojiMenu();
    });
    document.body.appendChild(emojiMenu);
    document.addEventListener("mousedown", function (e) {
      if (!emojiMenu.hidden && !emojiMenu.contains(e.target) &&
          !e.target.closest(".gte-emoji-open")) {
        closeEmojiMenu();
      }
    });
  }

  function setupEmojiMenus() {
    editor.querySelectorAll(".gte-emoji-open").forEach(function (button) {
      var input = button.parentNode.querySelector("input[data-type=glyph]");
      button.addEventListener("click", function () {
        if (!emojiMenu) buildEmojiMenu();
        if (!emojiMenu.hidden && emojiTarget === input) {
          closeEmojiMenu();
          return;
        }
        emojiTarget = input;
        var rect = button.getBoundingClientRect();
        emojiMenu.style.left = Math.max(8, rect.right + window.scrollX - 360) + "px";
        emojiMenu.style.top = (rect.bottom + window.scrollY + 4) + "px";
        emojiMenu.hidden = false;
        var first = emojiMenu.querySelector(".gte-emoji");
        if (first) first.focus();
      });
    });
  }

  // --------------------------------------------------------------- take from

  var sourcesEl = document.getElementById("gte-sources");
  var sources = sourcesEl ? JSON.parse(sourcesEl.textContent) : [];
  var propTypesEl = document.getElementById("gte-prop-types");
  var propTypes = propTypesEl ? JSON.parse(propTypesEl.textContent) : {};

  function splitComponents(components, wantColours) {
    var out = {};
    Object.keys(components || {}).forEach(function (comp) {
      Object.keys(components[comp]).forEach(function (prop) {
        var isColour = (propTypes[comp] || {})[prop] === "color";
        if (isColour === wantColours) {
          (out[comp] = out[comp] || {})[prop] = components[comp][prop];
        }
      });
    });
    return out;
  }

  function mergeComponents(a, b) {
    var out = JSON.parse(JSON.stringify(a));
    Object.keys(b).forEach(function (comp) {
      out[comp] = Object.assign(out[comp] || {}, b[comp]);
    });
    return out;
  }

  function setField(id, value) {
    var el = document.getElementById(id);
    if (el) el.value = value === undefined || value === null ? "" : value;
  }

  function takeFrom(source, part) {
    var data = source.data;
    var current = readJSON(hidden.components, {});
    if (part === "colors") {
      hidden.seeds.value = JSON.stringify(data.seeds || { light: {}, dark: {} });
      hidden.light.value = JSON.stringify(data.light_tokens || {});
      hidden.dark.value = JSON.stringify(data.dark_tokens || {});
      hidden.components.value = JSON.stringify(
        mergeComponents(splitComponents(current, false), splitComponents(data.components, true))
      );
      setField("id_color_scheme", data.color_scheme || "user");
    } else if (part === "shapes") {
      hidden.components.value = JSON.stringify(
        mergeComponents(splitComponents(current, true), splitComponents(data.components, false))
      );
      setField("id_radius_scale", data.radius_scale || "1.00");
      setField("id_spacing_scale", data.spacing_scale || "1.00");
    } else if (part === "fonts") {
      setField("id_font_sans", data.font_sans);
      setField("id_font_mono", data.font_mono);
      setField("id_font_heading", data.font_heading);
      setField("id_font_label", data.font_label);
      setField("id_font_field", data.font_field);
      setField("id_web_font_provider", data.web_font_provider || "bunny");
      setField("id_font_scale", data.font_scale || "1.00");
    }
    load();
    changed();
    updateWebfontWarning();
    var status = editor.querySelector("[data-take-status]");
    status.textContent = interpolate(
      gettext("taken", "Taken from “%(name)s” — not saved yet."),
      { name: source.name }
    );
  }

  function setupTakeFrom() {
    var box = editor.querySelector("[data-take]");
    if (!box) return;
    var select = box.querySelector("[data-take-source]");
    box.querySelectorAll("[data-take-part]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var source = sources.find(function (s) { return String(s.pk) === select.value; });
        if (source) takeFrom(source, btn.dataset.takePart);
      });
    });
  }

  // -------------------------------------------------------------- sections

  var SECTIONS_KEY = "grappelli-theme-editor:sections";

  function loadSectionState() {
    try {
      return JSON.parse(window.localStorage.getItem(SECTIONS_KEY) || "{}") || {};
    } catch (e) {
      if (e instanceof SyntaxError) return {}; // corrupted value: start over
      throw e;
    }
  }

  function setupSections() {
    var state = loadSectionState();
    editor.querySelectorAll("details.gte-section").forEach(function (d) {
      if (Object.prototype.hasOwnProperty.call(state, d.dataset.section)) {
        d.open = state[d.dataset.section];
      }
      d.addEventListener("toggle", function () {
        state[d.dataset.section] = d.open;
        window.localStorage.setItem(SECTIONS_KEY, JSON.stringify(state));
      });
    });
    editor.querySelectorAll("[data-expand-all]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var open = btn.dataset.expandAll === "1";
        btn.closest(".gte-tab-panel").querySelectorAll("details.gte-section")
          .forEach(function (d) { d.open = open; });
      });
    });
  }

  function showTab(name) {
    editor.querySelectorAll(".gte-tab").forEach(function (t) {
      var active = t.dataset.tab === name;
      t.classList.toggle("gte-tab-active", active);
      t.setAttribute("aria-selected", active ? "true" : "false");
    });
    editor.querySelectorAll(".gte-tab-panel").forEach(function (p) {
      p.hidden = p.dataset.panel !== name;
    });
  }

  // ------------------------------------------------------------- inspector
  //
  // Clicking an element in the preview reads the iframe's own stylesheets
  // (Grappelli's screen.css + the live theme CSS) to find which --grp-* /
  // --gte-* variables style that element's text, background, borders and
  // shadows, then highlights everything in the editor that changes them.

  var inspecting = true;
  var inspected = null;
  var inspectorEl = editor.querySelector("[data-inspector]");
  var CATEGORIES = [
    ["text", /^(color|-webkit-text-fill-color)$/],
    ["background", /^background/],
    ["border", /^(border|outline)/],
    ["shadow", /shadow$/],
  ];
  var VAR_RE = /var\(\s*(--(?:grp|gte)-[\w-]+)/g;
  var PSEUDO_ELEMENT_RE = /::?(before|after|placeholder|selection|marker|-webkit-[\w-]+|-moz-[\w-]+)/g;

  function splitSelectors(text) {
    var out = [], depth = 0, start = 0;
    for (var i = 0; i < text.length; i++) {
      var ch = text[i];
      if (ch === "(") depth++;
      else if (ch === ")") depth--;
      else if (ch === "," && depth === 0) {
        out.push(text.slice(start, i));
        start = i + 1;
      }
    }
    out.push(text.slice(start));
    return out;
  }

  function matches(node, selectorText) {
    return splitSelectors(selectorText).some(function (sel) {
      sel = sel.replace(PSEUDO_ELEMENT_RE, "").trim();
      if (!sel) return false;
      try {
        return node.matches(sel);
      } catch (e) {
        // Selectors the browser cannot evaluate (vendor pseudo-classes).
        if (e instanceof frame.contentWindow.DOMException || e instanceof DOMException) {
          return false;
        }
        throw e;
      }
    });
  }

  function styleRules(doc) {
    var win = doc.defaultView;
    var out = [];
    var walk = function (rules) {
      Array.prototype.forEach.call(rules, function (r) {
        if (r.selectorText !== undefined && r.style) {
          if (r.style.cssText.indexOf("var(--") !== -1) out.push(r);
        } else if (r.cssRules) {
          if (r.media && !win.matchMedia(r.media.mediaText).matches) return;
          walk(r.cssRules);
        }
      });
    };
    Array.prototype.forEach.call(doc.styleSheets, function (sheet) {
      var rules;
      try {
        rules = sheet.cssRules;
      } catch (e) {
        if (e.name === "SecurityError") return; // cross-origin sheet, unreadable
        throw e;
      }
      walk(rules);
    });
    return out;
  }

  function categoryOf(prop) {
    for (var i = 0; i < CATEGORIES.length; i++) {
      if (CATEGORIES[i][1].test(prop)) return CATEGORIES[i][0];
    }
    return null;
  }

  // -> {category: {depth, vars: [names]}}
  function collectVars(el) {
    var chain = [];
    for (var n = el; n && n.nodeType === 1; n = n.parentElement) chain.push(n);
    var best = {};
    styleRules(el.ownerDocument).forEach(function (rule) {
      var decls = [];
      rule.style.cssText.split(";").forEach(function (chunk) {
        var i = chunk.indexOf(":");
        if (i === -1) return;
        var prop = chunk.slice(0, i).trim();
        var value = chunk.slice(i + 1);
        if (prop.indexOf("--") === 0) return;
        var cat = categoryOf(prop);
        if (!cat) return;
        var names = [];
        value.replace(VAR_RE, function (_, name) { names.push(name); });
        if (names.length) decls.push([cat, names]);
      });
      if (!decls.length) return;
      for (var d = 0; d < chain.length; d++) {
        if (!matches(chain[d], rule.selectorText)) continue;
        decls.forEach(function (decl) {
          var cur = best[decl[0]];
          if (!cur || d < cur.depth) best[decl[0]] = { depth: d, vars: decl[1].slice() };
          else if (d === cur.depth) {
            decl[1].forEach(function (v) { if (cur.vars.indexOf(v) === -1) cur.vars.push(v); });
          }
        });
        break;
      }
    });
    return keepLive(chain, best);
  }

  var CATEGORY_LONGHANDS = {
    text: ["color"],
    background: ["background-color", "background-image"],
    border: [
      "border-top-color", "border-right-color", "border-bottom-color",
      "border-left-color", "outline-color",
    ],
    shadow: ["box-shadow", "text-shadow"],
  };

  // Several rules can match an element at the same depth while only one
  // wins the cascade (e.g. Grappelli's generic input rule also matches
  // submit buttons). Keep only --grp-* variables whose resolved colour
  // actually shows up in the element's computed style for that category.
  // --gte-* component variables are kept: they are the knob for it.
  function keepLive(chain, found) {
    var doc = chain[0].ownerDocument;
    var win = doc.defaultView;
    var probe = doc.createElement("span");
    probe.style.display = "none";
    doc.body.appendChild(probe);
    var normalize = function (value) {
      probe.style.color = "";
      probe.style.color = value;
      return probe.style.color ? win.getComputedStyle(probe).color : "";
    };
    Object.keys(found).forEach(function (cat) {
      var hit = found[cat];
      var node = chain[hit.depth];
      var computed = win.getComputedStyle(node);
      var actual = CATEGORY_LONGHANDS[cat].map(function (p) {
        return computed.getPropertyValue(p);
      }).join(" ");
      hit.vars = hit.vars.filter(function (name) {
        if (name.indexOf("--gte-") === 0) return true;
        var resolved = normalize(computed.getPropertyValue(name).trim());
        return resolved !== "" && actual.indexOf(resolved) !== -1;
      });
    });
    probe.remove();
    return found;
  }

  function componentHits(el) {
    var hits = [];
    editor.querySelectorAll("[data-comp-section]").forEach(function (section) {
      var sel = section.dataset.inspect;
      if (!sel || section.dataset.compSection === "general") return;
      var depth = 0;
      for (var n = el; n && n.nodeType === 1; n = n.parentElement, depth++) {
        if (matches(n, sel)) {
          hits.push({ key: section.dataset.compSection, depth: depth, section: section });
          return;
        }
      }
    });
    hits.sort(function (a, b) { return a.depth - b.depth; });
    return hits;
  }

  function seedFor(token, category) {
    var row = editor.querySelector('[data-token-row="' + token + '"]');
    if (!row) return null;
    var family = row.dataset[previewMode === "dark" ? "familyDark" : "familyLight"];
    if (family === "neutral") return category === "text" ? "text" : "background";
    if (family === "keep") return null;
    return family; // accent, danger, success, warning, chrome
  }

  function describe(el) {
    var name = el.tagName.toLowerCase();
    if (el.id) name += "#" + el.id;
    var classes = Array.prototype.filter.call(el.classList, function (c) {
      return c.indexOf("gte-") !== 0;
    });
    if (classes.length) name += "." + classes.slice(0, 3).join(".");
    return name;
  }

  function labelOf(node) {
    var th = node.querySelector("th, summary");
    var text = th ? th.firstChild.textContent : node.textContent;
    return text.trim();
  }

  function flash(node) {
    node.classList.remove("gte-flash");
    void node.offsetWidth; // restart the animation
    node.classList.add("gte-flash");
  }

  function reveal(node) {
    var panel = node.closest(".gte-tab-panel");
    if (panel) showTab(panel.dataset.panel);
    var details = node.closest("details");
    if (details) details.open = true;
    node.scrollIntoView({ block: "center", behavior: "smooth" });
    flash(node);
  }

  function chip(label, node) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "gte-chip";
    b.textContent = label;
    b.addEventListener("click", function () { reveal(node); });
    return b;
  }

  function clearHits() {
    editor.querySelectorAll(".gte-hit").forEach(function (n) {
      n.classList.remove("gte-hit", "gte-hit-primary");
    });
    editor.querySelectorAll(".gte-tab-badge").forEach(function (b) { b.remove(); });
  }

  function inspect(el) {
    clearHits();
    inspected = el;
    var found = collectVars(el);
    var tokenNodes = [], propNodes = [], seedNodes = [];
    var add = function (list, node) {
      if (node && list.indexOf(node) === -1) list.push(node);
    };
    CATEGORIES.forEach(function (c) {
      var hit = found[c[0]];
      if (!hit) return;
      hit.vars.forEach(function (name) {
        if (name.indexOf("--grp-") === 0) {
          add(tokenNodes, editor.querySelector('[data-token-row="' + name + '"]'));
          var seed = seedFor(name, c[0]);
          if (seed) add(seedNodes, editor.querySelector('[data-seed-row="' + seed + '"]'));
        } else {
          // --gte-<component>-<prop>
          var rest = name.slice(6);
          editor.querySelectorAll("[data-prop-row]").forEach(function (row) {
            if (row.dataset.propRow.replace(".", "-") === rest) add(propNodes, row);
          });
        }
      });
    });
    var comps = componentHits(el);

    seedNodes.concat(tokenNodes, propNodes).forEach(function (n) {
      n.classList.add("gte-hit");
      var d = n.closest("details");
      if (d) d.open = true;
    });
    comps.forEach(function (c, i) {
      c.section.classList.add("gte-hit");
      if (i === 0) {
        c.section.classList.add("gte-hit-primary");
        c.section.open = true;
      }
    });

    // tab badges
    editor.querySelectorAll(".gte-tab").forEach(function (tab) {
      var panel = editor.querySelector('[data-panel="' + tab.dataset.tab + '"]');
      var n = panel.querySelectorAll("tr.gte-hit, details.gte-hit").length;
      if (!n) return;
      var badge = document.createElement("span");
      badge.className = "gte-tab-badge";
      badge.textContent = n;
      tab.appendChild(badge);
    });

    // inspector panel
    var body = inspectorEl.querySelector("[data-inspector-body]");
    body.innerHTML = "";
    inspectorEl.querySelector("[data-inspected-name]").textContent = describe(el);
    var line = function (label, nodes) {
      if (!nodes.length) return;
      var p = document.createElement("div");
      p.className = "gte-inspector-line";
      var strong = document.createElement("strong");
      strong.textContent = label + ": ";
      p.appendChild(strong);
      nodes.forEach(function (n) { p.appendChild(chip(labelOf(n), n)); });
      body.appendChild(p);
    };
    line(gettext("baseColours", "Base colours"), seedNodes);
    line(gettext("components", "Shapes & bars"), comps.map(function (c) { return c.section; }).concat(propNodes));
    line(gettext("tokens", "Colour tokens"), tokenNodes);
    if (!body.childNodes.length) {
      body.textContent = gettext("nothing", "Nothing in this theme changes this element.");
    }
    inspectorEl.hidden = false;

    // Show the hits: stay on the current tab if it has any, otherwise jump
    // to the most specific tab that does; then scroll to and flash them.
    var hitSelector = ".gte-hit-primary, tr.gte-hit, details.gte-hit";
    var visible = editor.querySelector(".gte-tab-panel:not([hidden])");
    if (!visible || !visible.querySelector(hitSelector)) {
      var order = ["components", "icons", "colors", "tokens"];
      for (var i = 0; i < order.length; i++) {
        var panel = editor.querySelector('[data-panel="' + order[i] + '"]');
        if (panel.querySelector(hitSelector)) {
          showTab(order[i]);
          visible = panel;
          break;
        }
      }
    }
    if (visible) {
      var targets = visible.querySelectorAll("tr.gte-hit, details.gte-hit > summary");
      targets.forEach(flash);
      var first = visible.querySelector(hitSelector);
      if (first) first.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }

  function clearInspection() {
    clearHits();
    inspectorEl.hidden = true;
    var doc = frameDoc();
    if (doc) doc.querySelectorAll(".gte-picked").forEach(function (n) {
      n.classList.remove("gte-picked");
    });
    inspected = null;
  }

  function installInspector(doc) {
    if (doc._gteInspector) return;
    doc._gteInspector = true;
    var style = doc.createElement("style");
    style.textContent =
      "html.gte-inspecting, html.gte-inspecting *{cursor:crosshair !important}" +
      ".gte-hover{outline:2px dashed #e91e63 !important;outline-offset:1px !important}" +
      ".gte-picked{outline:3px solid #e91e63 !important;outline-offset:1px !important}";
    doc.head.appendChild(style);
    var hovered = null;
    doc.addEventListener("mouseover", function (e) {
      if (!inspecting) return;
      if (hovered) hovered.classList.remove("gte-hover");
      hovered = e.target;
      hovered.classList.add("gte-hover");
    }, true);
    doc.addEventListener("mouseout", function () {
      if (hovered) hovered.classList.remove("gte-hover");
      hovered = null;
    }, true);
    var swallow = function (e) {
      if (!inspecting) return;
      e.preventDefault();
      e.stopImmediatePropagation();
    };
    doc.addEventListener("mousedown", swallow, true);
    doc.addEventListener("click", function (e) {
      if (!inspecting) return;
      swallow(e);
      doc.querySelectorAll(".gte-picked").forEach(function (n) {
        n.classList.remove("gte-picked");
      });
      e.target.classList.add("gte-picked");
      inspect(e.target);
    }, true);
    doc.documentElement.classList.toggle("gte-inspecting", inspecting);
  }

  // ------------------------------------------------------------------- wiring

  // Translated strings are rendered by the server (json_script).
  var i18nEl = document.getElementById("gte-i18n");
  var i18n = i18nEl ? JSON.parse(i18nEl.textContent) : {};
  var gettext = function (key, fallback) { return i18n[key] || fallback; };
  var interpolate = function (fmt, obj) {
    return fmt.replace(/%\((\w+)\)s/g, function (_, k) { return obj[k]; });
  };

  colorWidgets().forEach(setupColor);
  editor.querySelectorAll(".gte-length").forEach(setupLength);
  editor.querySelectorAll("select[data-comp]").forEach(function (s) {
    s.addEventListener("change", changed);
  });

  // Regular model fields (fonts, scales, light/dark mode, custom CSS).
  form.addEventListener("input", function (e) {
    // Editor controls have their own handlers; everything else is a model field.
    if (e.target.closest("[data-role], [data-comp], [data-token-filter], .gte-preview, .gte-take")) {
      return;
    }
    changed();
  });
  form.addEventListener("submit", serialize);

  editor.querySelectorAll(".gte-tab").forEach(function (tab) {
    tab.addEventListener("click", function () { showTab(tab.dataset.tab); });
  });
  setupSections();
  setupTypography();
  setupTakeFrom();
  setupFontMenus();
  setupEmojiMenus();
  updateWebfontWarning();
  form.addEventListener("input", function (e) {
    if (/^id_(font_|web_font_provider)/.test(e.target.id)) {
      updateWebfontWarning();
    }
  });
  // Picking an icon should take effect: switch the matching mode on if it
  // is still on Grappelli's default.
  var ICON_MODES = {
    add_glyph: [["add_icon", ["grappelli", "hidden", "line"], "custom"]],
    search_glyph: [["search_icon", ["grappelli", "hidden", "line"], "custom"]],
    save_glyph: [["submit_style", ["text"], "icon_text"], ["submit_icons", ["white", "dark"], "emoji"]],
    continue_glyph: [["submit_style", ["text"], "icon_text"], ["submit_icons", ["white", "dark"], "emoji"]],
    addanother_glyph: [["submit_style", ["text"], "icon_text"], ["submit_icons", ["white", "dark"], "emoji"]],
    delete_glyph: [["submit_style", ["text"], "icon_text"], ["submit_icons", ["white", "dark"], "emoji"]],
  };
  ["save", "continue", "addanother", "delete"].forEach(function (name) {
    ICON_MODES[name + "_image"] = [["submit_style", ["text"], "icon_text"]];
  });
  editor.querySelectorAll("input[data-type=glyph], input[data-type=url]").forEach(function (input) {
    input.addEventListener("input", function () {
      (ICON_MODES[input.dataset.prop] || []).forEach(function (rule) {
        var select = editor.querySelector(
          'select[data-comp="' + input.dataset.comp + '"][data-prop="' + rule[0] + '"]'
        );
        if (input.value.trim() && select && rule[1].indexOf(select.value) !== -1) {
          select.value = rule[2];
        }
      });
      changed();
    });
  });

  var inspectToggle = editor.querySelector("[data-inspect-toggle]");
  inspectToggle.addEventListener("click", function () {
    inspecting = !inspecting;
    inspectToggle.classList.toggle("gte-active", inspecting);
    inspectToggle.setAttribute("aria-pressed", inspecting ? "true" : "false");
    var doc = frameDoc();
    if (doc) doc.documentElement.classList.toggle("gte-inspecting", inspecting);
    if (!inspecting) clearInspection();
  });
  editor.querySelector("[data-inspector-close]").addEventListener("click", clearInspection);

  editor.querySelectorAll("[data-preview-mode]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      previewMode = btn.dataset.previewMode;
      editor.querySelectorAll("[data-preview-mode]").forEach(function (b) {
        b.classList.toggle("gte-active", b === btn);
      });
      applyToFrame();
      if (inspected && inspected.isConnected) inspect(inspected);
    });
  });

  var filter = editor.querySelector("[data-token-filter]");
  if (filter) {
    filter.addEventListener("input", function () {
      var q = filter.value.trim().toLowerCase();
      editor.querySelectorAll("[data-token-row]").forEach(function (row) {
        var match = !q || row.dataset.tokenRow.indexOf(q) !== -1 ||
          row.textContent.toLowerCase().indexOf(q) !== -1;
        row.hidden = !match;
      });
      editor.querySelectorAll(".gte-token-group").forEach(function (g) {
        if (q) g.open = !!g.querySelector("[data-token-row]:not([hidden])");
      });
    });
  }

  frame.addEventListener("load", prepareFrame);

  load();
  serialize();
  refresh();
  if (frameDoc() && frameDoc().readyState === "complete") prepareFrame();
})();
