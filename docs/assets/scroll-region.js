/**
 * Make a horizontally scrolling table reachable and named for keyboard users.
 *
 * Material for MkDocs wraps every table in
 * `div.md-typeset__scrollwrap > div.md-typeset__table` in its own JavaScript,
 * at view time, so no build hook can reach the wrapper. Its CSS gives the
 * wrapper `overflow-x: auto`, but nothing makes it focusable, so a keyboard
 * user cannot scroll a wide table, and nothing names it. Material takes
 * critical fixes only, so the site does it here.
 *
 * Only a wrapper that overflows gets `tabindex="0"`, `role="region"` and an
 * `aria-label`: a table that fits would add a tab stop and a landmark that do
 * nothing. Whether it overflows depends on the window width, so a
 * ResizeObserver on the wrapper and its table re-checks it. The name is the
 * table's caption, else the nearest preceding heading, else "Table". Regions
 * share a page, so a second table under the same heading is "Heading, table 2"
 * and so on; a caption always wins and is never suffixed.
 *
 * The site may later move to Zensical. Port this file if it has no equivalent.
 */
(function () {
  "use strict";

  var observer = null;

  // The nearest heading before the wrap, else "Table".
  function headingNameOf(wrap) {
    var name = "Table";
    var headings = document.querySelectorAll(
      "[data-md-component=content] :is(h1, h2, h3, h4, h5, h6)"
    );
    for (var i = 0; i < headings.length; i++) {
      // Stop at the first heading after the table; keep the last one before it.
      if (!(headings[i].compareDocumentPosition(wrap) & Node.DOCUMENT_POSITION_FOLLOWING)) {
        break;
      }
      var heading = headings[i].cloneNode(true);
      heading.querySelectorAll(".headerlink").forEach(function (link) {
        link.remove();
      });
      name = heading.textContent.trim() || name;
    }
    return name;
  }

  function nameOf(wrap) {
    var caption = wrap.querySelector("caption");
    if (caption && caption.textContent.trim()) {
      return caption.textContent.trim();
    }
    var name = headingNameOf(wrap);
    // N is this table's place among the uncaptioned tables that share the
    // heading name. Counting every such table, not only those that overflow
    // now, keeps a name stable however the observer orders its updates.
    var n = 1;
    var wraps = document.querySelectorAll(".md-typeset__scrollwrap");
    for (var i = 0; i < wraps.length && wraps[i] !== wrap; i++) {
      if (!wraps[i].querySelector("caption") && headingNameOf(wraps[i]) === name) {
        n++;
      }
    }
    return n > 1 ? name + ", table " + n : name;
  }

  function update(wrap) {
    if (wrap.scrollWidth > wrap.clientWidth) {
      wrap.setAttribute("tabindex", "0");
      wrap.setAttribute("role", "region");
      wrap.setAttribute("aria-label", nameOf(wrap));
    } else {
      wrap.removeAttribute("tabindex");
      wrap.removeAttribute("role");
      wrap.removeAttribute("aria-label");
    }
  }

  // document$ is Material's observable: it emits on first load and again after
  // each instant navigation swaps in a new page.
  document$.subscribe(function () {
    if (observer) {
      observer.disconnect();
    }
    observer = new ResizeObserver(function (entries) {
      entries.forEach(function (entry) {
        update(entry.target.closest(".md-typeset__scrollwrap"));
      });
    });
    document.querySelectorAll(".md-typeset__scrollwrap").forEach(function (wrap) {
      observer.observe(wrap);
      observer.observe(wrap.firstElementChild);
    });
  });
})();
