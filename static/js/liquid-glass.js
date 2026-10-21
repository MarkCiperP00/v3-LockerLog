// Liquid-glass tiles: a soft light follows the mouse across the hovered tile.
(() => {
  if (matchMedia("(pointer: coarse)").matches) return;
  document.querySelectorAll(".liquid-glass.is-interactive").forEach(tile => {
    tile.addEventListener("pointermove", e => {
      const r = tile.getBoundingClientRect();
      tile.style.setProperty("--mx", `${e.clientX - r.left}px`);
      tile.style.setProperty("--my", `${e.clientY - r.top}px`);
    }, { passive: true });
  });
})();
