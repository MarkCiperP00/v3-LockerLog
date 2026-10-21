// Decorative "LockerLog" text grid behind the login and error pages.
// Cells near the mouse grow, lift and shift toward gold; the loop only runs while something moves.
(() => {
  const canvas = document.getElementById("text-grid");
  if (!canvas || !canvas.getContext) return;
  const stage = document.getElementById("brand-panel") || canvas.parentElement;
  const ctx = canvas.getContext("2d");

  const WORD = "LockerLog";
  const CELL_W = 118, CELL_H = 46;
  const FONT_SIZE = 15, FONT_GROW = 7, LIFT = 3;
  const RADIUS = 170, EASE = 0.14;
  const BASE_ALPHA = 0.09, ALPHA_GAIN = 0.55;
  const ROSE = [255, 214, 220], GOLD = [227, 199, 102];
  const FONT_FAMILY = '"DM Mono", ui-monospace, monospace';

  const interactive =
    !matchMedia("(prefers-reduced-motion: reduce)").matches &&
    !matchMedia("(pointer: coarse)").matches;

  let cells = [], width = 0, height = 0, dpr = 1;
  let pointer = null, frame = 0, resizeTimer = 0;

  function layout() {
    const rect = stage.getBoundingClientRect();
    width = rect.width;
    height = rect.height;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);

    const previous = new Map(cells.map(c => [c.key, c.v]));
    cells = [];
    for (let row = 0, y = CELL_H / 2; y < height + CELL_H; row++, y += CELL_H) {
      const offset = row % 2 ? CELL_W / 2 : 0;
      for (let col = 0, x = offset; x < width + CELL_W; col++, x += CELL_W) {
        const key = row + ":" + col;
        cells.push({ key, x, y, v: previous.get(key) || 0 });
      }
    }
  }

  const smoothstep = t => (t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t));
  const mix = (a, b, t) => Math.round(a + (b - a) * t);

  function draw() {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    // Resting cells share one font and colour, so draw them in a single pass.
    ctx.font = `500 ${FONT_SIZE}px ${FONT_FAMILY}`;
    ctx.fillStyle = `rgba(${ROSE.join(",")},${BASE_ALPHA})`;
    for (const c of cells) if (c.v < 0.002) ctx.fillText(WORD, c.x, c.y);

    for (const c of cells) {
      if (c.v < 0.002) continue;
      const v = c.v;
      ctx.font = `500 ${(FONT_SIZE + FONT_GROW * v).toFixed(2)}px ${FONT_FAMILY}`;
      ctx.fillStyle = `rgba(${mix(ROSE[0], GOLD[0], v)},${mix(ROSE[1], GOLD[1], v)},${mix(ROSE[2], GOLD[2], v)},${(BASE_ALPHA + v * ALPHA_GAIN).toFixed(3)})`;
      ctx.fillText(WORD, c.x, c.y - LIFT * v);
    }
  }

  function step() {
    let moving = false;
    for (const c of cells) {
      let target = 0;
      if (pointer) {
        const d = Math.hypot(c.x - pointer.x, c.y - pointer.y);
        if (d < RADIUS) target = smoothstep(1 - d / RADIUS);
      }
      const diff = target - c.v;
      if (Math.abs(diff) > 0.002) {
        c.v += diff * EASE;
        moving = true;
      } else {
        c.v = target;
      }
    }
    draw();
    frame = moving ? requestAnimationFrame(step) : 0;
  }

  const kick = () => { if (!frame) frame = requestAnimationFrame(step); };

  function onMove(e) {
    const rect = stage.getBoundingClientRect();
    pointer = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    kick();
  }
  function onLeave() { pointer = null; kick(); }
  function onResize() {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { layout(); draw(); }, 150);
  }
  function teardown() {
    cancelAnimationFrame(frame);
    frame = 0;
    clearTimeout(resizeTimer);
    window.removeEventListener("resize", onResize);
    stage.removeEventListener("pointermove", onMove);
    stage.removeEventListener("pointerleave", onLeave);
  }

  layout();
  draw();
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(draw);
  window.addEventListener("resize", onResize);
  window.addEventListener("pagehide", teardown, { once: true });
  if (interactive) {
    stage.addEventListener("pointermove", onMove, { passive: true });
    stage.addEventListener("pointerleave", onLeave);
  }
})();
