/**
 * CaP-X Main JavaScript
 * GSAP animations, scroll behavior, dynamic content injection
 */

// Prevent browser scroll restoration
if ("scrollRestoration" in history) {
  history.scrollRestoration = "manual";
}
window.scrollTo(0, 0);

document.addEventListener("DOMContentLoaded", () => {
  window.scrollTo(0, 0);
  injectDynamicContent();
  initNavbar();
  initAnimations();
  initAllCharts();
  initDemoModal();
  initDemoGalleryToggle();
});

window.addEventListener("load", () => {
  if (window.location.hash) {
    history.replaceState(null, "", window.location.pathname);
  }
  window.scrollTo(0, 0);

  // On mobile, scroll chart to the right to show latest data
  const chartPanel = document.querySelector(".chart-panel");
  if (chartPanel && window.innerWidth <= 768) {
    chartPanel.scrollLeft = chartPanel.scrollWidth;
  }
});

/* ==========================================
   Dynamic Content Injection from Config
   ========================================== */

function injectDynamicContent() {
  const cfg = SITE_CONFIG;

  // Hero tagline (eye-catching)
  const taglineEl = document.getElementById("hero-tagline");
  if (taglineEl) {
    taglineEl.innerHTML = `<span class="accent">${cfg.heroTaglinePrefix}</span> ${cfg.heroTagline}`;
  }

  // Paper title (in paper-details section)
  const titleEl = document.getElementById("paper-title");
  if (titleEl) {
    // Split "CaP-X:" as accent
    const parts = cfg.paperTitle.split(":");
    if (parts.length === 2) {
      titleEl.innerHTML = `<span class="accent">${parts[0]}:</span>${parts[1]}`;
    } else {
      titleEl.textContent = cfg.paperTitle;
    }
  }

  // Nav brand
  const brandEl = document.getElementById("nav-brand");
  if (brandEl) brandEl.textContent = cfg.paperTitle.split(":")[0] || "CaP-X";

  // Nav team
  const teamEl = document.getElementById("nav-team");
  if (teamEl) teamEl.textContent = cfg.teamName;

  // Nav links
  document.querySelectorAll("[data-link]").forEach(el => {
    const key = el.getAttribute("data-link");
    if (cfg.links[key]) el.href = cfg.links[key];
  });

  // Authors
  const authorsEl = document.getElementById("authors-list");
  if (authorsEl) {
    authorsEl.innerHTML = cfg.authors.map((a, i) => {
      const comma = i < cfg.authors.length - 1 ? "," : "";
      const star = a.equalContrib ? '<span class="equal-contrib">*</span>' : "";
      const affNums = a.affiliations.join(",");
      return `<span class="author">
        <a href="${a.url}" target="_blank" rel="noopener">${a.name}</a>${star}<span class="affiliation-nums">${affNums}</span>${comma}
      </span>`;
    }).join("\n");
  }

  // Equal contribution note
  const equalNote = document.getElementById("equal-note");
  if (equalNote) equalNote.textContent = "* Equal contribution";

  // Affiliations
  const affEl = document.getElementById("affiliations-list");
  if (affEl) {
    affEl.innerHTML = Object.entries(cfg.affiliations)
      .map(([num, name]) => `<span class="affiliation"><span class="aff-num">${num}</span>${name}</span>`)
      .join("\n");
  }

  // Institution logos
  const logosEl = document.getElementById("institution-logos");
  if (logosEl) {
    logosEl.innerHTML = cfg.institutionLogos
      .map(l => `<img class="institution-logo" src="${l.src}" alt="${l.name}" title="${l.name}">`)
      .join("\n");
  }
}

/* ==========================================
   Navbar Behavior
   ========================================== */

function initNavbar() {
  const navbar = document.querySelector(".navbar");
  if (!navbar) return;

  // Scroll class toggle
  const onScroll = () => {
    navbar.classList.toggle("scrolled", window.scrollY > 20);
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // Smooth scroll for anchor links
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener("click", e => {
      const target = document.querySelector(link.getAttribute("href"));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: "smooth" });
      }
    });
  });
}

/* ==========================================
   GSAP Animations
   ========================================== */

function initAnimations() {
  if (typeof gsap === "undefined" || typeof ScrollTrigger === "undefined") return;

  gsap.registerPlugin(ScrollTrigger);

  // Fade in sections
  gsap.utils.toArray(".fade-in").forEach(el => {
    gsap.fromTo(el,
      { opacity: 0, y: 30 },
      {
        opacity: 1, y: 0,
        duration: 0.8,
        ease: "power2.out",
        scrollTrigger: {
          trigger: el,
          start: "top 85%",
          once: true,
        },
      }
    );
  });

  // Slide up elements
  gsap.utils.toArray(".slide-up").forEach((el, i) => {
    gsap.fromTo(el,
      { opacity: 0, y: 50 },
      {
        opacity: 1, y: 0,
        duration: 0.7,
        delay: i * 0.1,
        ease: "power3.out",
        scrollTrigger: {
          trigger: el,
          start: "top 88%",
          once: true,
        },
      }
    );
  });

  // Scale in elements
  gsap.utils.toArray(".scale-in").forEach(el => {
    gsap.fromTo(el,
      { opacity: 0, scale: 0.92 },
      {
        opacity: 1, scale: 1,
        duration: 0.6,
        ease: "power2.out",
        scrollTrigger: {
          trigger: el,
          start: "top 85%",
          once: true,
        },
      }
    );
  });

  // Hero entrance animation
  const heroTl = gsap.timeline({ delay: 0.2 });
  heroTl
    .from("#hero-tagline", { opacity: 0, y: 30, duration: 0.8, ease: "power3.out" })
    .from(".hero-buttons", { opacity: 0, y: 15, duration: 0.5, ease: "power2.out" }, "-=0.3")
    .from("#institution-logos", { opacity: 0, y: 15, duration: 0.5, ease: "power2.out" }, "-=0.2");

  // Highlight cards staggered entrance
  gsap.utils.toArray(".highlight-card").forEach((card, i) => {
    gsap.fromTo(card,
      { opacity: 0, y: 40, scale: 0.97 },
      {
        opacity: 1, y: 0, scale: 1,
        duration: 0.7,
        ease: "power2.out",
        scrollTrigger: {
          trigger: card,
          start: "top 85%",
          once: true,
        },
      }
    );
  });

  // Feature pills staggered
  gsap.utils.toArray(".feature-pill").forEach((pill, i) => {
    gsap.fromTo(pill,
      { opacity: 0, y: 15, scale: 0.9 },
      {
        opacity: 1, y: 0, scale: 1,
        duration: 0.4,
        delay: i * 0.06,
        ease: "back.out(1.5)",
        scrollTrigger: {
          trigger: ".feature-pills",
          start: "top 88%",
          once: true,
        },
      }
    );
  });

  // Video placeholders
  gsap.utils.toArray(".video-placeholder").forEach((el, i) => {
    gsap.fromTo(el,
      { opacity: 0, y: 20 },
      {
        opacity: 1, y: 0,
        duration: 0.5,
        delay: i * 0.1,
        ease: "power2.out",
        scrollTrigger: {
          trigger: el,
          start: "top 90%",
          once: true,
        },
      }
    );
  });
}

/* ==========================================
   Demo Video Modal
   ========================================== */

function initDemoModal() {
  const overlay = document.getElementById("demo-modal");
  if (!overlay) return;

  const modalVideo = overlay.querySelector(".demo-modal-video");
  const modalTitle = overlay.querySelector(".demo-modal-title");
  const modalDesc = overlay.querySelector(".demo-modal-desc");
  const closeBtn = overlay.querySelector(".demo-modal-close");

  function openModal(card) {
    const source = card.querySelector("source");
    const label = card.querySelector(".demo-video-label");
    const caption = card.getAttribute("data-caption") || "";

    modalVideo.src = source ? source.getAttribute("src") : "";
    modalTitle.textContent = label ? label.textContent : "";
    modalDesc.textContent = caption;

    overlay.classList.add("active");
    const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;
    document.documentElement.style.overflow = "hidden";
    document.body.style.paddingRight = scrollbarWidth + "px";
  }

  function closeModal() {
    overlay.classList.remove("active");
    document.documentElement.style.overflow = "";
    document.body.style.paddingRight = "";
    modalVideo.removeAttribute("src");
  }

  document.querySelectorAll(".demo-video-card").forEach(card => {
    card.addEventListener("click", () => openModal(card));
  });

  closeBtn.addEventListener("click", e => {
    e.stopPropagation();
    closeModal();
  });

  overlay.addEventListener("click", e => {
    if (e.target === overlay) closeModal();
  });

  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && overlay.classList.contains("active")) {
      closeModal();
    }
  });
}

/* ==========================================
   Demo Gallery Collapse/Expand (mobile)
   ========================================== */

function initDemoGalleryToggle() {
  const gallery = document.querySelector(".demo-gallery");
  const toggle = document.getElementById("demo-gallery-toggle");
  if (!gallery || !toggle) return;

  function isMobile() {
    return window.matchMedia("(max-width: 768px)").matches;
  }

  // Collapse by default on mobile
  if (isMobile()) {
    gallery.classList.add("collapsed");
  }

  toggle.addEventListener("click", () => {
    const collapsed = gallery.classList.toggle("collapsed");
    toggle.textContent = collapsed ? "Show More" : "Show Less";
  });

  // Handle resize: add/remove collapsed
  window.addEventListener("resize", () => {
    if (!isMobile()) {
      gallery.classList.remove("collapsed");
    } else if (!gallery.classList.contains("collapsed") && toggle.textContent === "Show More") {
      gallery.classList.add("collapsed");
    }
  });
}
