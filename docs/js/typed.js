(function () {
  'use strict';
  var line = document.querySelector('.typed-line');
  if (!line) { return; }

  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)');
  if (reduced && reduced.matches) { return; }

  var lines;
  try { lines = JSON.parse(line.dataset.lines); } catch (e) { return; }
  if (!lines || lines.length < 2) { return; }

  var index = 0, at = lines[0].length, deleting = false, left = lines.length * 2;

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
      if (--left <= 0 && index === 0) { return; }
      deleting = true;
      return setTimeout(tick, 2600);
    }

    return setTimeout(tick, 45 + Math.random() * 55);
  }

  setTimeout(function () { deleting = true; tick(); }, 2600);
})();
