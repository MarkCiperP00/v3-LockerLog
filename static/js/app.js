// Fee preview on the request form: asks Flask (/api/fee) and shows the result.
const sem = document.getElementById("sem");
if (sem) {
  const box = document.getElementById("preview");
  const rate = sem.dataset.rate;
  sem.addEventListener("change", async () => {
    if (!sem.value) { box.textContent = `Rate: ₱${rate} per day`; return; }
    try {
      const r = await fetch("/api/fee?semester_id=" + encodeURIComponent(sem.value));
      const d = await r.json();
      box.textContent = d.error ? d.error
        : `${d.days} days (${d.start} to ${d.end}) × ₱${rate} = ₱${d.fee}`;
    } catch { box.textContent = "Could not compute the fee. Try again."; }
  });
}
// Ask before approve / reject / release / delete / cancel
document.querySelectorAll("form[data-confirm]").forEach(f =>
  f.addEventListener("submit", e => { if (!confirm(f.dataset.confirm)) e.preventDefault(); }));
// Fade out flash messages
setTimeout(() => document.querySelectorAll(".flash").forEach(m => m.classList.add("hide")), 5000);
