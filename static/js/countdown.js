/* Live countdown for "Acil Karar" polls.
   <span data-countdown data-seconds-left="123" data-end-text="Süre doldu" data-reload="POLL_ID">
   The server sends the seconds left, so a wrong clock on the visitor's device does not matter.
   With data-reload the page reloads once when the timer ends, which reveals the locked results. */
(function () {
  var elements = document.querySelectorAll("[data-countdown]");
  if (!elements.length) return;

  var startedAt = Date.now();
  var items = Array.prototype.map.call(elements, function (el) {
    return { el: el, end: startedAt + parseInt(el.dataset.secondsLeft, 10) * 1000, done: false };
  });

  function format(ms) {
    var total = Math.max(0, Math.ceil(ms / 1000));
    return Math.floor(total / 60) + ":" + String(total % 60).padStart(2, "0");
  }

  function finish(item) {
    item.done = true;
    var el = item.el;
    el.textContent = el.dataset.endText || "0:00";
    el.classList.add("is-done");
    var pollId = el.dataset.reload;
    if (!pollId) return;
    var key = "kararsizim-reloaded-" + pollId;
    try {
      if (sessionStorage.getItem(key)) return; // reload only once, never loop
      sessionStorage.setItem(key, "1");
    } catch (error) { /* storage blocked: still reload once below */ }
    setTimeout(function () { window.location.reload(); }, 1200);
  }

  var timer = setInterval(tick, 250);

  function tick() {
    var now = Date.now();
    var pending = false;
    items.forEach(function (item) {
      if (item.done) return;
      var left = item.end - now;
      if (left <= 0) { finish(item); return; }
      pending = true;
      item.el.textContent = format(left);
    });
    if (!pending) clearInterval(timer);
  }
  tick();
})();
