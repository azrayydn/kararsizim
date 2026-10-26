/* Toast notifications: Django messages slide in at the top right and disappear by themselves.
   Hovering or focusing a toast pauses its timer; the x button closes it right away. */
(function () {
  var toasts = document.querySelectorAll("[data-toast]");
  Array.prototype.forEach.call(toasts, function (toast) {
    var total = toast.classList.contains("toast--error") ? 7000 : 4500;
    var remaining = total;
    var startedAt = 0;
    var timer = null;
    var closed = false;

    toast.style.setProperty("--toast-ms", total + "ms");

    function close() {
      if (closed) return;
      closed = true;
      clearTimeout(timer);
      toast.classList.add("is-leaving");
      setTimeout(function () { toast.remove(); }, 250);
    }
    function start() {
      if (closed) return;
      startedAt = Date.now();
      timer = setTimeout(close, remaining);
    }
    function pause() {
      if (closed) return;
      clearTimeout(timer);
      remaining = Math.max(1000, remaining - (Date.now() - startedAt));
    }

    toast.addEventListener("mouseenter", pause);
    toast.addEventListener("mouseleave", start);
    toast.addEventListener("focusin", pause);
    toast.addEventListener("focusout", start);
    toast.querySelector("[data-toast-close]").addEventListener("click", close);
    start();
  });
})();
