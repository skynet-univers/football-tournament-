/* ==========================================================================
   APEX LEAGUE — main.js
   Handles: loading screen, navbar scroll/toggle, countdown timer,
   match tabs, scroll-reveal animations, footer year.
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
  initLoader();
  initNavbar();
  initCountdown();
  initTabs();
  initScrollReveal();
  initFooterYear();
});

/* ---------------------------------------------------------------------- */
/* Loading Screen                                                         */
/* ---------------------------------------------------------------------- */
function initLoader() {
  const loader = document.getElementById("loader");
  if (!loader) return;

  const hide = () => loader.classList.add("hidden");

  // Hide once the page has fully loaded, with a minimum display time
  // so the animation doesn't just flash on fast connections.
  const minDisplay = new Promise((resolve) => setTimeout(resolve, 600));
  const pageLoad = new Promise((resolve) => {
    if (document.readyState === "complete") resolve();
    else window.addEventListener("load", resolve);
  });

  Promise.all([minDisplay, pageLoad]).then(hide);

  // Safety net in case something stalls
  setTimeout(hide, 2500);
}

/* ---------------------------------------------------------------------- */
/* Navbar: scroll shadow + mobile toggle                                  */
/* ---------------------------------------------------------------------- */
function initNavbar() {
  const navbar = document.getElementById("navbar");
  const toggle = document.getElementById("navToggle");
  const links = document.getElementById("navLinks");

  if (navbar) {
    const onScroll = () => {
      navbar.classList.toggle("scrolled", window.scrollY > 20);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  if (toggle && links) {
    toggle.addEventListener("click", () => {
      toggle.classList.toggle("open");
      links.classList.toggle("open");
    });

    // Close mobile menu when a link is tapped
    links.querySelectorAll("a").forEach((a) => {
      a.addEventListener("click", () => {
        toggle.classList.remove("open");
        links.classList.remove("open");
      });
    });
  }
}

/* ---------------------------------------------------------------------- */
/* Countdown Timer (Overview page — next match)                           */
/* ---------------------------------------------------------------------- */
function initCountdown() {
  const el = document.getElementById("countdown");
  if (!el) return;

  const targetDate = new Date(el.dataset.datetime);
  const dEl = document.getElementById("cd-days");
  const hEl = document.getElementById("cd-hours");
  const mEl = document.getElementById("cd-minutes");
  const sEl = document.getElementById("cd-seconds");

  function pad(n) {
    return String(Math.max(n, 0)).padStart(2, "0");
  }

  function tick() {
    const now = new Date();
    let diff = Math.max(0, targetDate - now);

    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    diff -= days * 1000 * 60 * 60 * 24;
    const hours = Math.floor(diff / (1000 * 60 * 60));
    diff -= hours * 1000 * 60 * 60;
    const minutes = Math.floor(diff / (1000 * 60));
    diff -= minutes * 1000 * 60;
    const seconds = Math.floor(diff / 1000);

    if (dEl) dEl.textContent = pad(days);
    if (hEl) hEl.textContent = pad(hours);
    if (mEl) mEl.textContent = pad(minutes);
    if (sEl) sEl.textContent = pad(seconds);

    if (targetDate - now <= 0) {
      clearInterval(interval);
    }
  }

  tick();
  const interval = setInterval(tick, 1000);
}

/* ---------------------------------------------------------------------- */
/* Match Tabs (Matches page)                                              */
/* ---------------------------------------------------------------------- */
function initTabs() {
  const tabButtons = document.querySelectorAll(".tab-btn");
  if (!tabButtons.length) return;

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tab;

      tabButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      document.querySelectorAll(".tab-panel").forEach((panel) => {
        panel.classList.toggle("active", panel.id === `panel-${target}`);
      });
    });
  });
}

/* ---------------------------------------------------------------------- */
/* Scroll Reveal Animations                                               */
/* ---------------------------------------------------------------------- */
function initScrollReveal() {
  const items = document.querySelectorAll(".reveal");
  if (!items.length) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("in-view");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );

  items.forEach((item) => observer.observe(item));
}

/* ---------------------------------------------------------------------- */
/* Footer year                                                            */
/* ---------------------------------------------------------------------- */
function initFooterYear() {
  const yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = new Date().getFullYear();
}
