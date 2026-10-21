// After a successful login the card shows "Welcome <name>!". When the progress bar
// finishes (or Continue is clicked) the card fades out and the user's page opens.
(() => {
  const next = document.getElementById("welcome-continue");
  if (!next) return;
  const panel = document.getElementById("welcome");
  const progress = document.getElementById("welcome-progress");
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let leaving = false;

  function leave() {
    if (leaving) return;
    leaving = true;
    panel.classList.add("is-leaving");
    setTimeout(() => location.replace(next.href), reduce ? 0 : 220);
  }

  next.addEventListener("click", e => { e.preventDefault(); leave(); });
  if (reduce || !progress) {
    setTimeout(leave, 2000);
  } else {
    progress.addEventListener("animationend", leave, { once: true });
    setTimeout(leave, 4000);   // safety net if animationend never fires (e.g. background tab)
  }
})();

// Show / hide the password on the login form.
(() => {
  const toggle = document.getElementById("password-toggle");
  const input = toggle && document.getElementById(toggle.getAttribute("aria-controls"));
  if (!input) return;
  toggle.addEventListener("click", () => {
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    toggle.textContent = show ? "Hide" : "Show";
    toggle.setAttribute("aria-pressed", String(show));
    toggle.setAttribute("aria-label", show ? "Hide password" : "Show password");
  });
})();
