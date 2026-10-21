/* A few small conveniences. Everything works without this file. */
(function () {
  'use strict';

  var SCROLL_KEY = 'nextup:scroll';

  function openSeasons() {
    var out = [];
    document.querySelectorAll('details.season[data-season]').forEach(function (box) {
      if (box.open) { out.push(box.getAttribute('data-season')); }
    });
    return out;
  }

  function rememberPage() {
    try {
      window.sessionStorage.setItem(SCROLL_KEY, JSON.stringify({
        path: window.location.pathname,
        y: window.scrollY || document.documentElement.scrollTop || 0,
        seasons: openSeasons()
      }));
    } catch (error) {  }
  }

  function takeRememberedPage() {
    var raw = null;
    try {
      raw = window.sessionStorage.getItem(SCROLL_KEY);
      window.sessionStorage.removeItem(SCROLL_KEY);
    } catch (error) { return null; }
    if (!raw) { return null; }
    var saved = null;
    try { saved = JSON.parse(raw); } catch (error) { return null; }
    if (!saved || saved.path !== window.location.pathname) { return null; }
    return saved;
  }

  document.addEventListener('submit', rememberPage, true);

  var remembered = takeRememberedPage();

  if (remembered && remembered.seasons) {
    var wanted_seasons = remembered.seasons;
    document.querySelectorAll('details.season[data-season]').forEach(function (box) {
      box.open = wanted_seasons.indexOf(box.getAttribute('data-season')) !== -1;
    });
  }

  var wanted = remembered ? (remembered.y > 0 ? remembered.y : 0) : 0;
  if (wanted) {
    window.scrollTo(0, wanted);

    var moved = false;
    var noteMove = function () { moved = true; };
    ['wheel', 'touchstart', 'keydown', 'mousedown'].forEach(function (name) {
      window.addEventListener(name, noteMove, { passive: true, once: true });
    });
    window.addEventListener('load', function () {
      if (!moved) { window.scrollTo(0, wanted); }
    });
  }

  document.querySelectorAll('form[data-confirm] button').forEach(function (button) {
    var original = button.textContent.trim();
    var armed = false;
    var timer = null;

    button.addEventListener('click', function (event) {
      if (armed) { return; }
      event.preventDefault();
      armed = true;
      button.textContent = button.dataset.confirmLabel || 'Click again to confirm';
      button.classList.add('btn-danger');
      button.classList.remove('btn-quiet');
      timer = window.setTimeout(function () {
        armed = false;
        button.textContent = original;
        button.classList.remove('btn-danger');
        button.classList.add('btn-quiet');
      }, 5000);
    });

    button.addEventListener('blur', function () {
      if (!armed) { return; }
      window.clearTimeout(timer);
      armed = false;
      button.textContent = original;
      button.classList.remove('btn-danger');
      button.classList.add('btn-quiet');
    });
  });

  document.querySelectorAll('form[data-autosave]').forEach(function (form) {
    var button = form.querySelector('button[type="submit"], button:not([type])');
    if (button) { button.hidden = true; }
    var pending = null;
    form.addEventListener('change', function () {
      window.clearTimeout(pending);

      pending = window.setTimeout(function () { rememberPage(); form.submit(); }, 250);
    });
  });

  var clockToggle = document.querySelector('.clock-toggle');
  if (clockToggle) {
    var go = clockToggle.querySelector('.clock-toggle-go');
    if (go) { go.hidden = true; }
    clockToggle.addEventListener('change', function (event) {
      if (event.target && event.target.name === 'clock_format') {
        var form = document.getElementById('clock-form');
        if (form) { rememberPage(); form.submit(); }
      }
    });
  }

  document.addEventListener('keydown', function (event) {
    if (event.key !== '/' || event.metaKey || event.ctrlKey || event.altKey) { return; }
    var tag = (document.activeElement && document.activeElement.tagName) || '';
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') { return; }
    var box = document.getElementById('q');
    if (box) { event.preventDefault(); box.focus(); box.select(); }
  });
})();
