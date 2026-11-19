(() => {
  const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const PHONE = /^\+?\d[\d\s\-()]{9,17}$/;

  const messageFor = (el) => {
    const v = el.value.trim();
    if (el.required && v === "") return "Заполните это поле.";
    if (v === "") return "";
    if (el.dataset.type === "email" && !EMAIL.test(v)) return "Введите e-mail в формате name@example.com.";
    if (el.dataset.type === "phone" && !PHONE.test(v)) return "Введите телефон в формате +7 900 123-45-67.";
    const min = parseInt(el.getAttribute("minlength") || "0", 10);
    const max = parseInt(el.getAttribute("maxlength") || "0", 10);
    if (min && v.length < min) return `Введите не менее ${min} символов (сейчас ${v.length}).`;
    if (max && v.length > max) return `Не более ${max} символов.`;
    return "";
  };

  const show = (el, text) => {
    const box = document.querySelector(`[data-error-for="${el.id}"]`);
    el.classList.toggle("is-error", Boolean(text));
    if (text) el.setAttribute("aria-invalid", "true");
    else el.removeAttribute("aria-invalid");
    if (box) { box.textContent = text; box.hidden = !text; }
  };

  document.querySelectorAll("form[data-validate]").forEach((form) => {
    const fields = [...form.querySelectorAll("input, textarea, select")]
      .filter((el) => el.name && el.type !== "hidden" && el.type !== "checkbox");
    fields.forEach((el) => {
      el.addEventListener("blur", () => show(el, messageFor(el)));
      el.addEventListener("input", () => { if (el.classList.contains("is-error")) show(el, messageFor(el)); });
    });
    form.addEventListener("submit", (event) => {
      let first = null;
      fields.forEach((el) => {
        const text = messageFor(el);
        show(el, text);
        if (text && !first) first = el;
      });
      if (first) { event.preventDefault(); first.focus(); }
    });
  });
})();