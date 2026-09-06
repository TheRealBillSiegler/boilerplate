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
 * - securityLevel: 'strict' prevents script injection (all diagrams are author-controlled)
 * - Scoped MutationObserver monitors only [data-theme] attribute changes
 * - Defensive existence checks prevent undefined errors
 * - Error boundary with structured logging for observability
 * - No user-generated content processed (trust boundary: author-controlled markdown only)
 * - The written script tag's URL has no attacker-controlled input (derived
 *   from this script's own src, same directory, fixed filename)
 *
 * TRUST BOUNDARY:
 * All Mermaid diagrams originate from author-controlled markdown files in docs/.
 * No diagrams are generated from user input or external sources.
 * This justifies 'strict' security level vs 'antiscript'.
 *
 * DESIGN RATIONALE:
 * - Uses contentLoaded() instead of re-initialize() to avoid diagram flashing
 * - Material theme detection via [data-theme] attribute (Material for MkDocs standard)
 * - Explicit theme mapping: 'slate' → 'dark', others → 'default'
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

  /**
   * Detect current theme from Material for MkDocs theme switcher.
   * Material sets [data-theme] attribute on <html> element.
   *
   * @returns {string} Mermaid theme identifier ('dark' or 'default')
   */
  function getMermaidTheme() {
    const htmlElement = document.documentElement;
    if (!htmlElement) {
      console.warn('[Mermaid Theme] document.documentElement not available');
      return 'default';
    }

    const materialTheme = htmlElement.getAttribute('data-theme');

    // Material theme 'slate' maps to Mermaid 'dark' theme
    // All other values (including 'default', null, '') map to Mermaid 'default' theme
    return materialTheme === 'slate' ? 'dark' : 'default';
  }

  /**
   * Define theme variables to improve contrast across light/dark modes.
   * Targets timeline readability and general diagram clarity.
   *
   * @param {string} themeName - Mermaid theme identifier
   * @returns {Object} Mermaid themeVariables configuration
   */
  function getThemeVariables(themeName) {
    if (themeName === 'dark') {
      return {
        background: '#0f1115',
        // Use light pastel fills with dark text for readability on dark canvas.
        primaryColor: '#c7d2fe',
        primaryBorderColor: '#94a3b8',
        primaryTextColor: '#0b1324',
        secondaryColor: '#fde68a',
        secondaryBorderColor: '#b45309',
        secondaryTextColor: '#0b1324',
        tertiaryColor: '#fbcfe8',
        tertiaryBorderColor: '#be185d',
        tertiaryTextColor: '#0b1324',
        lineColor: '#94a3b8',
        textColor: '#e6edf3',
        // Timeline/Gantt color scales (cScale0..cScale4)
        cScale0: '#c7d2fe',
        cScale1: '#fde68a',
        cScale2: '#bbf7d0',
        cScale3: '#fbcfe8',
        cScale4: '#bae6fd',
        cScaleLabel: '#0b1324',
        fontFamily: '"IBM Plex Sans", "Segoe UI", Tahoma, Arial, sans-serif'
      };
    }

    return {
      background: '#ffffff',
      primaryColor: '#f5f7fb',
      primaryBorderColor: '#1f2937',
      primaryTextColor: '#0b1324',
      secondaryColor: '#eef2ff',
      secondaryBorderColor: '#1d4ed8',
      secondaryTextColor: '#0b1324',
      tertiaryColor: '#f1f5f9',
      tertiaryBorderColor: '#475569',
      tertiaryTextColor: '#0b1324',
      lineColor: '#475569',
      textColor: '#0b1324',
      fontFamily: '"IBM Plex Sans", "Segoe UI", Tahoma, Arial, sans-serif'
    };
  }

  /**
   * Initialize Mermaid with security-hardened configuration.
   * Called once on page load and when theme changes.
   */
  function initializeMermaid() {
    if (typeof mermaid === 'undefined') {
      console.error('[Mermaid Theme] Mermaid library not loaded. Ensure the vendored bundle loaded before initialization.');
      return;
    }

    try {
      const currentTheme = getMermaidTheme();

      mermaid.initialize({
        startOnLoad: true,
        theme: currentTheme,
        themeVariables: getThemeVariables(currentTheme),

        // SECURITY: 'strict' mode prevents script injection and dangerous features
        // Safe for author-controlled diagrams; blocks <script>, JS execution, etc.
        securityLevel: 'strict',

        // Suppress debug output in production (error-level only for observability)
        logLevel: 'error',

        // Disable flowchart HTML labels (additional XSS mitigation)
        flowchart: {
          htmlLabels: false
        }
      });

      console.info(`[Mermaid Theme] Initialized with theme: ${currentTheme}`);

      // Trigger re-render of existing diagrams after theme change
      // contentLoaded() is preferred over full re-initialization
      if (typeof mermaid.contentLoaded === 'function') {
        mermaid.contentLoaded();
      }

    } catch (error) {
      console.error('[Mermaid Theme] Initialization failed:', error);
    }
  }

  /**
   * Watch Material theme changes and re-initialize Mermaid.
   * MutationObserver scoped to [data-theme] attribute only (minimal attack surface).
   */
  function watchThemeChanges() {
    const themeObserver = new MutationObserver(function(mutations) {
      // Verify mutation is actually [data-theme] change (defensive check)
      const themeChanged = mutations.some(function(mutation) {
        return mutation.type === 'attributes' &&
               mutation.attributeName === 'data-theme';
      });

      if (themeChanged) {
        console.info('[Mermaid Theme] Theme toggle detected, re-initializing');
        initializeMermaid();
      }
    });

    // Observe only [data-theme] attribute changes on <html> element
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'], // SECURITY: Scope observation to single attribute
      childList: false,
      subtree: false
    });
  }

  /**
   * Entry point: initialize Mermaid once the vendored bundle (written above,
   * synchronously, when this page has diagrams) has loaded.
   */
  function boot() {
    if (!pageHasMermaidDiagrams()) {
      return;
    }
    initializeMermaid();
    watchThemeChanges();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

})();
