/**
 * Home-page demo: plays the scripted terminal recording, respecting
 * prefers-reduced-motion.
 *
 * A page that sets `demo: true` in its front matter (the home page) embeds
 * the scripted terminal demo as an asciicast, played back by the self-hosted
 * asciinema-player (docs/assets/asciinema/); overrides/main.html adds the
 * player's stylesheet and these scripts to that page. A
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
    // No cols or rows: the player takes the terminal size from the cast's
    // header, which scripts/record_demo.py writes, so a re-record at another
    // size cannot crop the session.
    AsciinemaPlayer.create({ data: window.BOILERPLATE_DEMO_CAST }, el, {
      fit: "width",
      preload: true,
      autoPlay: !reduced,
      loop: !reduced,
      controls: "auto",
      idleTimeLimit: 2,
      // A poster is only wanted when playback will not start on its own;
      // with autoplay it shows for a beat before the first frame, which
      // reads as a flash of the wrong moment. One second in, the recording
      // is on its title card, the banner.
      poster: reduced ? "npt:0:01" : undefined,
      terminalFontFamily: "'JetBrains Mono', monospace",
    });
  }

  // overrides/main.html emits this script after Material's bundle, so
  // document$ (which Material exports whether or not navigation.instant is
  // on) is defined here and the subscribe branch runs; it emits once the
  // DOM is ready and again on every instant-navigation page swap. The
  // DOMContentLoaded and immediate branches only cover a page that loads
  // this script without the bundle, such as a local preview of the HTML.
  if (typeof document$ !== "undefined" && document$ && typeof document$.subscribe === "function") {
    document$.subscribe(initDemoCast);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDemoCast);
  } else {
    initDemoCast();
  }
})();
