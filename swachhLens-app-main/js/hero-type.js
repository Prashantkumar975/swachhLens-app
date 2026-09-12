/* =========================================================
 * SwachhLens — Hero Typewriter Animation
 * ---------------------------------------------------------
 * Animates the hero headline word-by-word, then types out
 * the accent word ("report.") letter by letter with a
 * blinking cursor. Pure CSS + minimal JS, no dependencies.
 *
 * The h1 must have:
 *   data-hero-type
 *   data-hero-phrase="A cleaner city starts with one report."
 *   data-hero-accent="report."
 *
 * When the i18n engine (js/lang.js) is present, the phrase
 * and accent are read from the hero.h1 / hero.h1accent keys
 * instead (falling back to the data attributes), and the
 * animation re-runs whenever the language changes.
 * ========================================================= */
(function () {
  var root = document.querySelector('[data-hero-type]');
  if (!root) return;

  var textEl = root.querySelector('[data-hero-type-text]');
  var accentEl = root.querySelector('[data-hero-type-accent]');
  if (!textEl || !accentEl) return;

  var timers = [];

  function clearTimers() {
    timers.forEach(function (t) { clearTimeout(t); });
    timers = [];
  }

  function translate(key) {
    if (window.t) return window.t(key) || '';
    return '';
  }

  function run() {
    clearTimers();
    textEl.textContent = '';
    accentEl.textContent = '';

    var phrase = translate('hero.h1') || root.getAttribute('data-hero-phrase') || 'A cleaner city starts with one report.';
    var accent = translate('hero.h1accent') || root.getAttribute('data-hero-accent') || 'report.';

    var accentIdx = phrase.indexOf(accent);
    if (accentIdx < 0) accentIdx = phrase.length;
    var before = phrase.slice(0, accentIdx);

    // Split the "before" part into words
    var words = before.split(/\s+/).filter(Boolean);
    var delay = 0;
    var wordDelay = 140; // ms between words (softer cadence)

    // Animate words appearing one by one
    words.forEach(function (word, i) {
      timers.push(setTimeout(function () {
        var span = document.createElement('span');
        span.className = 'hero-word';
        span.textContent = word;
        textEl.appendChild(span);
        textEl.appendChild(document.createTextNode('\u00A0')); // non-breaking space
      }, delay));
      delay += wordDelay;
    });

    // After all words appear, fade in the accent word (CSS animates it in)
    timers.push(setTimeout(function () {
      accentEl.textContent = accent;
      accentEl.style.animation = 'none';
      // Force reflow so the CSS keyframe restarts cleanly
      void accentEl.offsetWidth;
      accentEl.style.animation = '';
    }, delay + 80));
  }

  run();
  document.addEventListener('swachlens:lang', run);
})();