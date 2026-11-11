// Comportamiento mínimo del lado del cliente. Todo lo demás lo hace HTMX desde el servidor.
"use strict";

// 1) Buscador instantáneo de la lista: filtra las tarjetas por nombre mientras escribes.
document.addEventListener("input", (event) => {
  const input = event.target;
  if (!(input instanceof HTMLInputElement) || !input.dataset.filter) return;
  const needle = normalize(input.value);
  for (const item of document.querySelectorAll(input.dataset.filter)) {
    item.hidden = needle !== "" && !normalize(item.dataset.name || "").includes(needle);
  }
});

function normalize(text) {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

// 2) Tras un alta rápida, cerrar el desplegable y vaciar el formulario.
document.addEventListener("htmx:afterRequest", (event) => {
  const form = event.target;
  if (form instanceof HTMLFormElement && form.dataset.resetOnSuccess !== undefined && event.detail.successful) {
    form.reset();
    form.closest("details")?.removeAttribute("open");
  }
});

// 3) Confirmación antes de acciones que se deshacen con dificultad (sin JS en línea: CSP).
document.addEventListener("submit", (event) => {
  const form = event.target;
  if (form instanceof HTMLFormElement && form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
    event.preventDefault();
  }
});

// 4) Service worker para que la app se pueda instalar y aguante mala cobertura.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}
