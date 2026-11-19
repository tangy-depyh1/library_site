document.addEventListener("DOMContentLoaded", () => {
  const input = document.querySelector("[data-live-url]");
  const list = document.getElementById("live-results");
  if (!input || !list) return;
  let timer = null;
  let controller = null;

  const close = () => { list.hidden = true; };
  const note = (text) => {
    const li = document.createElement("li");
    li.className = "live-results__note";
    li.textContent = text;
    return li;
  };
  const render = (results) => {
    list.replaceChildren();
    if (!results.length) list.append(note("Ничего не найдено"));
    results.forEach((r) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = r.url;
      const title = document.createElement("strong");
      title.textContent = r.title;
      const meta = document.createElement("span");
      meta.className = "meta";
      meta.textContent = `${r.authors} · ${r.free > 0 ? "свободно " + r.free : "все выданы"}`;
      a.append(title, meta);
      li.append(a);
      list.append(li);
    });
    list.hidden = false;
  };
  const search = async () => {
    const q = input.value.trim();
    if (q.length < 2) { close(); return; }
    if (controller) controller.abort();
    controller = new AbortController();
    list.replaceChildren(note("Загрузка…"));
    list.hidden = false;
    try {
      const response = await fetch(`${input.dataset.liveUrl}?q=${encodeURIComponent(q)}`, { signal: controller.signal });
      if (!response.ok) throw new Error("bad response");
      render((await response.json()).results);
    } catch (error) {
      if (error.name !== "AbortError") list.replaceChildren(note("Не удалось выполнить поиск. Повторите позже."));
    }
  };

  input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(search, 300); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  document.addEventListener("click", (e) => { if (!e.target.closest(".live")) close(); });
});