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

// Ask before approve / reject / release / delete / cancel.
// Uses the confirm dialog from the app layout; falls back to window.confirm.
const confirmDialog = document.getElementById("confirm-modal");
let pendingForm = null;
document.querySelectorAll("form[data-confirm]").forEach(f =>
  f.addEventListener("submit", e => {
    e.preventDefault();
    if (!confirmDialog || typeof confirmDialog.showModal !== "function") {
      if (confirm(f.dataset.confirm)) f.submit();
      return;
    }
    pendingForm = f;
    document.getElementById("confirm-modal-message").textContent = f.dataset.confirm;
    confirmDialog.returnValue = "";
    confirmDialog.showModal();
  }));
if (confirmDialog) {
  confirmDialog.addEventListener("close", () => {
    // form.submit() skips the submit listener, so this does not reopen the dialog.
    if (confirmDialog.returnValue === "confirm" && pendingForm) pendingForm.submit();
    pendingForm = null;
  });
  // Click on the backdrop closes like Cancel.
  confirmDialog.addEventListener("click", e => { if (e.target === confirmDialog) confirmDialog.close("cancel"); });
}

// Manage Lockers: open the edit dialog filled with the row's locker
const editDialog = document.getElementById("edit-locker");
if (editDialog) {
  document.querySelectorAll("[data-edit-locker]").forEach(btn =>
    btn.addEventListener("click", () => {
      const id = btn.dataset.editLocker;
      document.getElementById("edit-locker-id").value = id;
      document.getElementById("edit-locker-label").textContent = id;
      document.getElementById("edit-building").value = btn.dataset.building;
      document.getElementById("edit-floor").value = btn.dataset.floor;
      editDialog.showModal();
    }));
  editDialog.querySelectorAll("[data-dialog-close]").forEach(b => b.addEventListener("click", () => editDialog.close()));
  editDialog.addEventListener("click", e => { if (e.target === editDialog) editDialog.close(); });
}

// Dismiss flash messages
document.querySelectorAll("[data-flash-dismiss]").forEach(btn =>
  btn.addEventListener("click", () => {
    const msg = btn.closest(".flash");
    msg.classList.add("hide");
    setTimeout(() => msg.remove(), matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 200);
  }));
