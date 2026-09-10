/**
 * Mermaid Theme Integration (Zero Trust Configuration)
 *
 * Implements theme-aware Mermaid diagram rendering with hardened security controls
 * aligned to zero trust principles and repository security standards.
 *
 * LAZY LOADING:
 * The vendored Mermaid bundle (assets/mermaid.min.js) is no longer loaded on
 * every page via extra_javascript. This script checks the page for a
 * `.mermaid` element first and, only when one exists, loads the bundle
 * itself — resolving its URL from document.currentScript.src (same
 * directory as this script) so it works from any page depth and from the
 * offline bundle (file://) without a hardcoded path. Pages with no diagram
 * pay no cost: no request, no parse, no init.
 *
 * The load uses document.write() to insert a same-origin, parser-blocking
 * <script src> tag while this script is still being parsed inline — the
 * same mechanism a static extra_javascript entry would use, just applied
 * conditionally. This matters: Material's own bundle.js has native Mermaid
 * support that checks `typeof mermaid` when it processes `.mermaid`
 * elements and, finding it undefined, fetches Mermaid from unpkg.com. A
 * non-blocking load (a dynamically created <script> appended to <head>, or
 * a fetch/XHR) loses that race — it resolves after Material's own check has
 * already run, so unpkg gets hit anyway, defeating the point of vendoring.
 * document.write() blocks the parser (and so blocks Material's own script
 * further down the page, and DOMContentLoaded) until the vendored bundle
 * has loaded, which is what actually prevents the unpkg fallback. Chrome's
 * "slow-connection" intervention against document.write()-injected scripts
 * only targets cross-origin scripts; this one is same-origin, so it is
 * unaffected. A synchronous XHR was considered instead and rejected: it
 * cannot load file:// URLs (blocked by CORS), which would break the
 * offline bundle.
 *
 * SECURITY POSTURE:
 * - The written script tag's URL has no attacker-controlled input (derived
 *   from this script's own src, same directory, fixed filename)
 * - This script never calls the Mermaid API; Material's own bundle renders
 *   and themes every `.mermaid` element, so there is no separate
 *   security-relevant configuration left here to hold
 *
 * TRUST BOUNDARY:
 * All Mermaid diagrams originate from author-controlled markdown files in docs/.
 * No diagrams are generated from user input or external sources.
 * This justifies 'strict' security level vs 'antiscript'.
 *
 * DESIGN RATIONALE:
 * Material for MkDocs already renders and themes Mermaid diagrams on its
 * own — see the LAZY LOADING note above for how it finds `mermaid` and
 * skips the unpkg.com fetch this script exists to prevent. Once the
 * vendored bundle has loaded, this script's job is done.
 *
 * SCOPE — FULL PAGE LOADS ONLY:
 * The document.write() call above only runs once, during the parse of the
 * page that requested this script. extra_javascript entries are not
 * re-executed on navigation.instant page swaps, so if that Material feature
 * is ever enabled for the online build (mkdocs.yml notes it as a possible
 * future step once the offline bundle no longer needs a separate config),
 * a diagram page reached by an instant navigation would find
 * `typeof mermaid === 'undefined'` here and fall through to Material's own
 * unpkg.com fetch — this file would need a document$.subscribe()-driven
 * reload path (subscribe to Material's document$ observable) before
 * navigation.instant lands.
 */

(function() {
  'use strict';

  // Only valid synchronously, while this script is executing.
  var currentScript = document.currentScript;

  /**
   * Whether this page has any Mermaid diagram to render.
   *
   * @returns {boolean} True if a `.mermaid` element exists in the document.
   */
  function pageHasMermaidDiagrams() {
    return document.querySelector('.mermaid') !== null;
  }

  /**
   * Resolve the vendored bundle's URL from this script's own location, so it
   * loads correctly regardless of page depth or the offline (file://) bundle.
   *
   * @returns {string|null} The bundle URL, or null if it cannot be resolved.
   */
  function resolveBundleUrl() {
    if (!currentScript || !currentScript.src) {
      return null;
    }
    return new URL('mermaid.min.js', currentScript.src).toString();
  }

  // Load the vendored bundle synchronously, before this script (and the
  // parser) moves on — see the LAZY LOADING note above for why this must be
  // blocking rather than a dynamically appended <script> or a fetch/XHR.
  if (pageHasMermaidDiagrams()) {
    var bundleUrl = resolveBundleUrl();
    if (bundleUrl) {
      document.write('<script src="' + bundleUrl.replace(/"/g, '&quot;') + '"><\/script>');
    } else {
      console.error('[Mermaid Theme] Could not resolve the vendored bundle location from document.currentScript.');
    }
  }

})();
