document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("favorite-btn");
  if (!btn) return;
  const status = document.getElementById("favorite-status");
  const label = btn.querySelector("[data-label]");
  const token = document.querySelector('meta[name="csrf-token"]').content;

  btn.addEventListener("click", async () => {
    const previous = label.textContent;
    btn.disabled = true;
    label.textContent = "Сохраняем…";
    try {
      const response = await fetch(btn.dataset.url, {
        method: "POST",
        headers: { "X-CSRFToken": token, "X-Requested-With": "XMLHttpRequest" },
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || "Не удалось выполнить действие. Повторите позже.");
      btn.setAttribute("aria-pressed", String(data.favorite));
      label.textContent = data.favorite ? "В избранном" : "В избранное";
      status.textContent = data.favorite ? "Книга добавлена в избранное." : "Книга убрана из избранного.";
    } catch (error) {
      label.textContent = previous;
      status.textContent = error.message;
    } finally {
      btn.disabled = false;
    }
  });
});