/* A few small conveniences. Everything works without this file. */
(function () {
  'use strict';

  var SCROLL_KEY = 'nextup:scroll';

  function rememberScroll() {
    try {
      window.sessionStorage.setItem(SCROLL_KEY, JSON.stringify({
        path: window.location.pathname,
        y: window.scrollY || document.documentElement.scrollTop || 0
      }));
    } catch (error) {  }
  }

  function takeRememberedScroll() {
    var raw = null;
    try {
      raw = window.sessionStorage.getItem(SCROLL_KEY);
      window.sessionStorage.removeItem(SCROLL_KEY);
    } catch (error) { return 0; }
    if (!raw) { return 0; }
    var saved = null;
    try { saved = JSON.parse(raw); } catch (error) { return 0; }
    if (!saved || saved.path !== window.location.pathname) { return 0; }
    return saved.y > 0 ? saved.y : 0;
  }

  document.addEventListener('submit', rememberScroll, true);

  var wanted = takeRememberedScroll();
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

      pending = window.setTimeout(function () { rememberScroll(); form.submit(); }, 250);
    });
  });

  var clockToggle = document.querySelector('.clock-toggle');
  if (clockToggle) {
    var go = clockToggle.querySelector('.clock-toggle-go');
    if (go) { go.hidden = true; }
    clockToggle.addEventListener('change', function (event) {
      if (event.target && event.target.name === 'clock_format') {
        var form = document.getElementById('clock-form');
        if (form) { rememberScroll(); form.submit(); }
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
