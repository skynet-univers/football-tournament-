/* ==========================================================================
   APEX LEAGUE — main.js
   Handles: loading screen, navbar scroll/toggle, countdown timer,
   match tabs, scroll-reveal animations, footer year.
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
  initLoader();
  initNavbar();
  initCountdown();
  initLiveMatchSync();
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
  const featuredStatus = document.getElementById("featured-status");
  const featuredMatch = document.getElementById("featured-match");

  // Keep the normal pre-match countdown when the Overview page has one.
  let targetDate = el ? new Date(el.dataset.datetime) : null;
  let lastServerStatus = featuredMatch?.dataset.initialStatus || null;
  let lastFeaturedId = featuredMatch?.dataset.matchId || null;

  function pad(n) {
    return String(Math.max(n, 0)).padStart(2, "0");
  }

  function renderCountdown(target) {
    if (!target || !el) return;

    const now = new Date();
    let diff = Math.max(0, target - now);

    const dEl = document.getElementById("cd-days");
    const hEl = document.getElementById("cd-hours");
    const mEl = document.getElementById("cd-minutes");
    const sEl = document.getElementById("cd-seconds");

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
  }

  async function refreshFeaturedMatch() {
    try {
      const response = await fetch("/api/countdown", { cache: "no-store" });
      if (!response.ok) return;

      const data = await response.json();

      if (!data.has_match) {
        // If the page currently shows a match, reload so it can show the
        // correct empty/upcoming state.
        if (featuredMatch) window.location.reload();
        return;
      }

      const serverStatus = data.status;

      // The featured match itself changed (for example, the previous live
      // match finished and the next fixture became featured).
      if (lastFeaturedId && String(data.id) !== String(lastFeaturedId)) {
        window.location.reload();
        return;
      }

      // The server has moved the match between Upcoming/Live/Finished.
      // Reload once so the existing page structure changes correctly.
      if (lastServerStatus && serverStatus !== lastServerStatus) {
        window.location.reload();
        return;
      }

      lastServerStatus = serverStatus;
      lastFeaturedId = String(data.id);

      if (data.datetime) {
        targetDate = new Date(data.datetime);
      }

      if (featuredStatus) {
        if (data.status === "live") {
          featuredStatus.className = "pill pill-live";
          featuredStatus.innerHTML = `<span class="live-dot"></span> LIVE — ${data.label}`;
        } else if (data.status === "upcoming") {
          featuredStatus.className = "pill pill-upcoming";
          featuredStatus.textContent = "Upcoming";
          renderCountdown(targetDate);
        }
      }
    } catch (error) {
      // Keep the page usable if a polling request temporarily fails.
      console.warn("Match timer update failed:", error);
    }
  }

  if (el && targetDate) {
    renderCountdown(targetDate);
    setInterval(() => renderCountdown(targetDate), 1000);
  }

  // The backend is the source of truth for match phase and status.
  refreshFeaturedMatch();
  setInterval(refreshFeaturedMatch, 1000);
}

/* ---------------------------------------------------------------------- */
/* Live match timing sync                                                 */
/* ---------------------------------------------------------------------- */
function initLiveMatchSync() {
  const cards = document.querySelectorAll(".js-match-card");
  const hasMatchCards = cards.length > 0;

  function phaseText(item) {
    if (item.phase === "halftime") return "● LIVE — Half Time";
    if (item.phase === "extra_time_halftime") return "● LIVE — Extra Time Half Time";
    if (item.phase === "finished") return "Full Time";
    if (item.status === "live") return `● LIVE — ${item.label}`;
    return "Upcoming";
  }

  async function refresh() {
    try {
      const response = await fetch("/api/match-statuses", { cache: "no-store" });
      if (!response.ok) return;

      const data = await response.json();
      const currentCards = document.querySelectorAll(".js-match-card");
      const byId = new Map(data.matches.map((m) => [String(m.id), m]));

      // If a match has just entered/leaved live state, reload the page so it
      // moves between the correct tabs.
      for (const card of currentCards) {
        const id = card.dataset.matchId;
        const previous = card.dataset.initialStatus;
        const current = byId.get(String(id));

        if (current && current.status !== previous) {
          window.location.reload();
          return;
        }

        if (!current && previous !== "finished") {
          // It may have just become finished and therefore disappeared from
          // the live/upcoming API response.
          if (previous === "live" || previous === "upcoming") {
            window.location.reload();
            return;
          }
        }
      }

      // If a new live match appeared while the page was open, reload so it
      // appears in the Live tab.
      const currentIds = new Set(
        [...currentCards].map((card) => String(card.dataset.matchId))
      );
      if (data.matches.some((m) => m.status === "live" && !currentIds.has(String(m.id)))) {
        window.location.reload();
        return;
      }

      // Update the displayed live minute/phase without reloading.
      currentCards.forEach((card) => {
        const item = byId.get(String(card.dataset.matchId));
        const label = card.querySelector(".js-match-status");
        if (!item || !label) return;

        label.textContent = phaseText(item);
      });
    } catch (error) {
      console.warn("Live match sync failed:", error);
    }
  }

  if (hasMatchCards) {
    refresh();
    setInterval(refresh, 1000);
  }
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
