/* A few small conveniences. Everything works without this file. */
(function () {
  'use strict';

  var SCROLL_KEY = 'nextup:scroll';

  function rememberPage() {
    try {
      window.sessionStorage.setItem(SCROLL_KEY, JSON.stringify({
        path: window.location.pathname,
        y: window.scrollY || document.documentElement.scrollTop || 0
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

  document.querySelectorAll('form[data-confirm]').forEach(function (form) {
    var live = document.createElement('span');
    live.className = 'visually-hidden';
    live.setAttribute('aria-live', 'polite');
    form.appendChild(live);

    Array.prototype.filter.call(form.elements, function (el) {
      return el.tagName === 'BUTTON';
    }).forEach(function (button) {
      var original = button.textContent.trim();
      var originalLabel = button.getAttribute('aria-label');
      var armed = false;
      var timer = null;

      function disarm() {
        window.clearTimeout(timer);
        armed = false;
        button.textContent = original;
        if (originalLabel) { button.setAttribute('aria-label', originalLabel); }
        button.classList.remove('btn-danger');
        button.classList.add('btn-quiet');
        live.textContent = '';
      }

      button.addEventListener('click', function (event) {
        if (armed) {
          var sure = document.createElement('input');
          sure.type = 'hidden';
          sure.name = 'sure';
          sure.value = '1';
          form.appendChild(sure);
          return;
        }
        event.preventDefault();
        armed = true;
        var label = button.dataset.confirmLabel || 'Click again to confirm';
        button.textContent = label;
        if (originalLabel) { button.setAttribute('aria-label', label); }
        button.classList.add('btn-danger');
        button.classList.remove('btn-quiet');
        live.textContent = label;
        timer = window.setTimeout(disarm, 5000);
      });

      button.addEventListener('blur', function () { if (armed) { disarm(); } });
    });
  });

  var zone = '';
  try { zone = Intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch (e) { zone = ''; }
  document.querySelectorAll('input[data-timezone]').forEach(function (input) { input.value = zone; });
  if (zone) {
    document.querySelectorAll('[data-needs-timezone]').forEach(function (el) { el.hidden = false; });
  }

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
    if (event.code !== 'Slash' || !event.altKey || event.ctrlKey || event.metaKey) { return; }
    var box = document.getElementById('q');
    if (box) { event.preventDefault(); box.focus(); box.select(); }
  });
})();
