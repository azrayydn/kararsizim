/* Poll creation form: add / remove option rows (2 to 5) and live character counter.
   The server validates everything again; this only makes the form pleasant to use. */
(function () {
  var form = document.querySelector("[data-poll-form]");
  if (!form) return;

  var min = parseInt(form.dataset.min, 10);
  var max = parseInt(form.dataset.max, 10);
  var list = form.querySelector("[data-option-list]");
  var template = form.querySelector("[data-option-template]");
  var addButton = form.querySelector("[data-add-option]");
  var maxHint = form.querySelector("[data-max-hint]");

  function rows() {
    return list.querySelectorAll("[data-option-row]");
  }

  function refresh() {
    var all = rows();
    all.forEach(function (row, index) {
      var input = row.querySelector("input");
      input.placeholder = "Seçenek " + (index + 1);
      input.setAttribute("aria-label", "Seçenek " + (index + 1));
      row.querySelector("[data-remove-option]").hidden = all.length <= min;
    });
    var full = all.length >= max;
    addButton.disabled = full;
    maxHint.hidden = !full;
  }

  addButton.addEventListener("click", function () {
    if (rows().length >= max) return;
    list.appendChild(template.content.cloneNode(true));
    refresh();
    var all = rows();
    all[all.length - 1].querySelector("input").focus();
  });

  list.addEventListener("click", function (event) {
    var button = event.target.closest("[data-remove-option]");
    if (!button || rows().length <= min) return;
    button.closest("[data-option-row]").remove();
    refresh();
  });

  var question = form.querySelector("textarea");
  var counter = form.querySelector("[data-counter]");
  if (question && counter) {
    var update = function () { counter.textContent = question.value.length; };
    question.addEventListener("input", update);
    update();
  }

  // ---- optional photo: preview and early (friendly) checks; the server checks again
  var fileInput = form.querySelector("[data-photo-input]");
  var preview = form.querySelector("[data-photo-preview]");
  var removeButton = form.querySelector("[data-photo-remove]");
  var photoError = form.querySelector("[data-photo-error]");
  var maxBytes = parseInt(form.dataset.photoMax, 10);
  var allowed = ["image/jpeg", "image/png", "image/webp"];

  function clearPhoto() {
    fileInput.value = "";
    if (preview.src) URL.revokeObjectURL(preview.src);
    preview.removeAttribute("src");
    preview.hidden = true;
    removeButton.hidden = true;
  }

  if (fileInput && preview && removeButton) {
    fileInput.addEventListener("change", function () {
      photoError.textContent = "";
      var file = fileInput.files[0];
      if (!file) { clearPhoto(); return; }
      if (allowed.indexOf(file.type) === -1) {
        clearPhoto();
        photoError.textContent = "Sadece JPG, PNG veya WebP yükleyebilirsin.";
        return;
      }
      if (file.size > maxBytes) {
        clearPhoto();
        photoError.textContent = "Fotoğraf en fazla 3 MB olabilir.";
        return;
      }
      if (preview.src) URL.revokeObjectURL(preview.src);
      preview.src = URL.createObjectURL(file);
      preview.hidden = false;
      removeButton.hidden = false;
    });
    removeButton.addEventListener("click", function () {
      photoError.textContent = "";
      clearPhoto();
    });
  }

  refresh();
})();
