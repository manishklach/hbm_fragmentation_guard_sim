const header = document.querySelector("[data-header]");
const navToggle = document.querySelector("[data-nav-toggle]");
const siteNav = document.getElementById("site-nav");
const navLinks = Array.from(document.querySelectorAll("[data-nav-link]"));
const sections = Array.from(document.querySelectorAll("[data-section]"));
const copyButtons = document.querySelectorAll("[data-copy-target]");
const counterGroups = document.querySelectorAll("[data-counter-group]");

const syncHeaderState = () => {
  if (!header) return;
  header.classList.toggle("is-scrolled", window.scrollY > 8);
};

syncHeaderState();
window.addEventListener("scroll", syncHeaderState, { passive: true });

if (navToggle && siteNav) {
  navToggle.addEventListener("click", () => {
    const expanded = navToggle.getAttribute("aria-expanded") === "true";
    navToggle.setAttribute("aria-expanded", String(!expanded));
    siteNav.classList.toggle("is-open", !expanded);
  });
}

navLinks.forEach((link) => {
  link.addEventListener("click", (event) => {
    const href = link.getAttribute("href") || "";
    if (!href.startsWith("#")) return;
    const target = document.querySelector(href);
    if (!target) return;
    event.preventDefault();
    const y = target.getBoundingClientRect().top + window.scrollY - 82;
    window.scrollTo({ top: y, behavior: "smooth" });
    siteNav?.classList.remove("is-open");
    navToggle?.setAttribute("aria-expanded", "false");
  });
});

const setActiveNav = (id) => {
  navLinks.forEach((link) => {
    link.classList.toggle("is-active", link.getAttribute("href") === `#${id}`);
  });
};

if ("IntersectionObserver" in window && sections.length) {
  const sectionObserver = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible?.target?.id) setActiveNav(visible.target.id);
    },
    { rootMargin: "-35% 0px -45% 0px", threshold: [0.2, 0.4, 0.6] }
  );
  sections.forEach((section) => sectionObserver.observe(section));
}

const formatCounterValue = (value, node) => {
  const decimals = Number(node.dataset.decimals || 0);
  const prefix = node.dataset.prefix || "";
  const suffix = node.dataset.suffix || "";
  const rendered = decimals ? value.toFixed(decimals) : Math.round(value).toString();
  return `${prefix}${rendered}${suffix}`;
};

const animateCounter = (node) => {
  if (node.dataset.animated === "true") return;
  node.dataset.animated = "true";
  const target = Number(node.dataset.target || 0);
  const duration = 1400;
  const start = performance.now();

  const tick = (now) => {
    const elapsed = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - elapsed, 3);
    node.textContent = formatCounterValue(target * eased, node);
    if (elapsed < 1) requestAnimationFrame(tick);
    else node.textContent = formatCounterValue(target, node);
  };

  requestAnimationFrame(tick);
};

if ("IntersectionObserver" in window) {
  const counterObserver = new IntersectionObserver(
    (entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.querySelectorAll("[data-counter]").forEach(animateCounter);
        observer.unobserve(entry.target);
      });
    },
    { threshold: 0.3 }
  );
  counterGroups.forEach((group) => counterObserver.observe(group));
}

const copyText = async (text) => {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return true;
  }
  const helper = document.createElement("textarea");
  helper.value = text;
  helper.setAttribute("readonly", "");
  helper.style.position = "absolute";
  helper.style.left = "-9999px";
  document.body.appendChild(helper);
  helper.select();
  const success = document.execCommand("copy");
  document.body.removeChild(helper);
  return success;
};

copyButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    const targetId = button.getAttribute("data-copy-target");
    const source = targetId ? document.getElementById(targetId) : null;
    if (!source) return;
    const label = button.textContent;
    try {
      await copyText(source.textContent || "");
      button.textContent = "Copied";
      window.setTimeout(() => {
        button.textContent = label;
      }, 1400);
    } catch {
      button.textContent = "Unable to copy";
      window.setTimeout(() => {
        button.textContent = label;
      }, 1400);
    }
  });
});
