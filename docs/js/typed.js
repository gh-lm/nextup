(function () {
  'use strict';
  var line = document.querySelector('.typed-line');
  if (!line) { return; }

  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)');
  if (reduced && reduced.matches) { return; }   // leave the first answer standing

  var lines;
  try { lines = JSON.parse(line.dataset.lines); } catch (e) { return; }
  if (!lines || lines.length < 2) { return; }

  var index = 0, at = lines[0].length, deleting = false;

  function tick() {
    var text = lines[index];
    if (deleting) {
      at -= 1;
      line.textContent = text.slice(0, at);
      if (at === 0) {
        deleting = false;
        index = (index + 1) % lines.length;
        return setTimeout(tick, 260);
      }
      return setTimeout(tick, 22);
    }
    at += 1;
    line.textContent = text.slice(0, at);
    if (at === text.length) {
      deleting = true;
      return setTimeout(tick, 2600);
    }
    // A touch of unevenness, so it reads as typing rather than a machine.
    return setTimeout(tick, 45 + Math.random() * 55);
  }

  setTimeout(function () { deleting = true; tick(); }, 2600);
})();
