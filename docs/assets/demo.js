/**
 * Home-page demo: plays the scripted terminal recording, respecting
 * prefers-reduced-motion.
 *
 * The home page embeds the scripted terminal demo as an asciicast, played
 * back by the self-hosted asciinema-player (docs/assets/asciinema/). A
 * viewer who has asked their OS for reduced motion gets a static poster
 * frame with manual playback controls instead of autoplaying, looping
 * playback.
 *
 * The recording is passed in as data (window.BOILERPLATE_DEMO_CAST, set by
 * boilerplate-new-cast.js) rather than as a URL for the player to fetch():
 * fetch() of a relative path is blocked from a null origin, so a URL source
 * cannot play at all when the offline bundle is opened from file://. A
 * plain <script src> loading the cast's own JS wrapper has no such
 * restriction, and the mechanism is identical for the online site.
 */
(function () {
  "use strict";

  function prefersReducedMotion() {
    return Boolean(
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  function initDemoCast() {
    var el = document.getElementById("demo-cast");
    if (!el || typeof AsciinemaPlayer === "undefined" || !window.BOILERPLATE_DEMO_CAST) {
      return;
    }
    // Instant-navigation can call this again on the same element; skip a
    // second player instead of stacking one on top of another.
    if (el.querySelector(".ap-wrapper")) {
      return;
    }
    var reduced = prefersReducedMotion();
    AsciinemaPlayer.create({ data: window.BOILERPLATE_DEMO_CAST }, el, {
      cols: 100,
      rows: 28,
      fit: "width",
      preload: true,
      autoPlay: !reduced,
      loop: !reduced,
      controls: "auto",
      idleTimeLimit: 2,
      // A poster is only wanted when playback will not start on its own;
      // with autoplay it shows for a beat before the first frame, which
      // reads as a flash of the wrong moment.
      poster: reduced ? "npt:0:04" : undefined,
      terminalFontFamily: "'JetBrains Mono', monospace",
    });
  }

  // Material exports document$ whether or not navigation.instant is on, but
  // its bundle loads after page-content scripts, so document$ is undefined
  // when this runs and the DOMContentLoaded branch is what executes today.
  // The document$ branch only takes effect if this script moves to
  // extra_javascript (loaded after the bundle).
  if (typeof document$ !== "undefined" && document$ && typeof document$.subscribe === "function") {
    document$.subscribe(initDemoCast);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDemoCast);
  } else {
    initDemoCast();
  }
})();
