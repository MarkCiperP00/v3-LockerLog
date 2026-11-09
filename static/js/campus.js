// Campus map: hovering a building (or its card) lifts that building and its name tag;
// clicking zooms gently toward it and opens its locker page.
(() => {
  const map = document.querySelector("[data-campus-map]");
  if (!map) return;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const buildings = [...map.querySelectorAll(".campus-bldg")];
  const labels = [...map.querySelectorAll(".campus-label")];
  const cards = [...document.querySelectorAll(".campus-pick")];
  let active = null;
  let leaving = false;

  function setActive(slug) {
    if (leaving || slug === active) return;
    active = slug;
    buildings.forEach(el => el.classList.toggle("is-active", el.dataset.building === slug));
    labels.forEach(el => el.classList.toggle("is-active", el.dataset.label === slug));
    cards.forEach(el => el.classList.toggle("is-active", el.dataset.building === slug));
  }

  function go(event, slug, href) {
    // Let the browser handle new-tab / new-window clicks normally.
    if (event.defaultPrevented || event.button > 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (reduce || !href) return;
    event.preventDefault();
    setActive(slug);
    leaving = true;
    const label = labels.find(el => el.dataset.label === slug);
    if (label) map.style.setProperty("--leave-origin", `${label.style.left} ${label.style.top}`);
    map.classList.add("is-leaving");
    setTimeout(() => { location.href = href; }, 240);
  }

  buildings.forEach(el => {
    const slug = el.dataset.building;
    el.addEventListener("pointerenter", () => setActive(slug));
    el.addEventListener("pointerleave", () => setActive(null));
    el.addEventListener("focus", () => setActive(slug));
    el.addEventListener("blur", () => setActive(null));
    el.addEventListener("click", e => go(e, slug, el.getAttribute("href")));
  });

  cards.forEach(el => {
    const slug = el.dataset.building;
    el.addEventListener("pointerenter", () => setActive(slug));
    el.addEventListener("pointerleave", () => { if (document.activeElement !== el) setActive(null); });
    el.addEventListener("focus", () => setActive(slug));
    el.addEventListener("blur", () => setActive(null));
    el.addEventListener("click", e => go(e, slug, el.getAttribute("href")));
  });

  // Coming back with the browser's Back button can restore the faded-out page from cache.
  window.addEventListener("pageshow", e => {
    if (!e.persisted) return;
    leaving = false;
    map.classList.remove("is-leaving");
    setActive(null);
  });
})();

// Building page: show all lockers or only one status; hide floors left empty.
(() => {
  const chips = document.querySelectorAll("[data-locker-filter] [data-filter]");
  const floors = document.querySelector("[data-locker-floors]");
  if (!chips.length || !floors) return;
  const empty = floors.querySelector("[data-filter-empty]");

  chips.forEach(chip => chip.addEventListener("click", () => {
    const filter = chip.dataset.filter;
    chips.forEach(c => c.setAttribute("aria-pressed", String(c === chip)));
    floors.dataset.filter = filter;
    let shown = 0;
    floors.querySelectorAll(".campus-floor").forEach(section => {
      const has = filter === "all" || section.querySelector(`li[data-status="${filter}"]`);
      section.classList.toggle("is-filtered-out", !has);
      if (has) shown++;
    });
    if (empty) empty.classList.toggle("hidden", shown > 0);
  }));
})();
