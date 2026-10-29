(() => {
  const sidebar = document.getElementById("app-sidebar");
  const openBtn = document.getElementById("nav-open");
  const closeBtn = document.getElementById("nav-close");
  const overlay = document.getElementById("nav-overlay");
  if (!sidebar || !openBtn) return;

  const desktop = matchMedia("(min-width: 1024px)");
  const focusable = () =>
    sidebar.querySelectorAll('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])');

  function open() {
    sidebar.dataset.open = "true";
    overlay.classList.remove("hidden");
    openBtn.setAttribute("aria-expanded", "true");
    document.body.classList.add("overflow-hidden");
    sidebar.setAttribute("role", "dialog");
    sidebar.setAttribute("aria-modal", "true");
    (closeBtn || focusable()[0]).focus();
    document.addEventListener("keydown", onKey);
  }

  function close(restoreFocus = true) {
    if (sidebar.dataset.open !== "true") return;
    delete sidebar.dataset.open;
    overlay.classList.add("hidden");
    openBtn.setAttribute("aria-expanded", "false");
    document.body.classList.remove("overflow-hidden");
    sidebar.removeAttribute("role");
    sidebar.removeAttribute("aria-modal");
    document.removeEventListener("keydown", onKey);
    if (restoreFocus) openBtn.focus();
  }

  function onKey(e) {
    if (e.key === "Escape") { e.preventDefault(); close(); return; }
    if (e.key !== "Tab") return;
    const items = focusable();
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  openBtn.addEventListener("click", open);
  if (closeBtn) closeBtn.addEventListener("click", () => close());
  overlay.addEventListener("click", () => close());
  desktop.addEventListener("change", e => { if (e.matches) close(false); });
})();
