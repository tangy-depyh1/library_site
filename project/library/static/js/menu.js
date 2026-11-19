document.addEventListener("DOMContentLoaded", () => {
  const button = document.querySelector(".menu-toggle");
  const nav = document.getElementById("main-nav");
  if (!button || !nav) return;
  button.addEventListener("click", () => {
    const open = nav.classList.toggle("is-open");
    button.setAttribute("aria-expanded", String(open));
  });
});