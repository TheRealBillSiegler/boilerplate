/**
 * Mermaid Theme Integration (Zero Trust Configuration)
 * 
 * Implements theme-aware Mermaid diagram rendering with hardened security controls
 * aligned to zero trust principles and repository security standards.
 * 
 * SECURITY POSTURE:
 * - securityLevel: 'strict' prevents script injection (all diagrams are author-controlled)
 * - Scoped MutationObserver monitors only [data-theme] attribute changes
 * - Defensive existence checks prevent undefined errors
 * - Error boundary with structured logging for observability
 * - No user-generated content processed (trust boundary: author-controlled markdown only)
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
 */

(function() {
  'use strict';
  
  // Defensive check: Ensure Mermaid library loaded before initialization
  if (typeof mermaid === 'undefined') {
    console.error('[Mermaid Theme] Mermaid library not loaded. Ensure mermaid.min.js loads before this script.');
    return;
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

  // Initial setup on page load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeMermaid);
  } else {
    // DOM already loaded (script loaded late)
    initializeMermaid();
  }

  /**
   * Monitor Material theme changes and re-initialize Mermaid.
   * MutationObserver scoped to [data-theme] attribute only (minimal attack surface).
   */
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

})();
