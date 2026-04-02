const WORDS_PER_MINUTE = 250;

function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

function updateProgressBar() {
  const root = document.documentElement;
  const progress = document.getElementById("progress-bar");
  if (!progress) return;
  const scrollable = root.scrollHeight - root.clientHeight;
  const ratio = scrollable <= 0 ? 0 : root.scrollTop / scrollable;
  progress.style.width = `${Math.min(100, Math.max(0, ratio * 100))}%`;
}

function escapeHtml(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function highlightCodeBlocks() {
  const blocks = document.querySelectorAll("pre code");
  blocks.forEach((block) => {
    const raw = block.textContent || "";
    let html = escapeHtml(raw);
    html = html.replace(
      /(^|\n)(\s*#.*?)(?=\n|$)/g,
      (match, prefix, comment) => `${prefix}<span class="token-comment">${comment}</span>`
    );
    html = html.replace(
      /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g,
      '<span class="token-string">$1</span>'
    );
    html = html.replace(
      /\b(def|class|import|from|return|if|else|for|in|and|or|not|True|False|None|git|python|pip|source|cd)\b/g,
      '<span class="token-keyword">$1</span>'
    );
    block.innerHTML = html;
  });
}

function addCopyButtons() {
  document.querySelectorAll("pre").forEach((pre) => {
    const button = document.createElement("button");
    button.className = "copy-button";
    button.type = "button";
    button.textContent = "Copy";
    button.addEventListener("click", async () => {
      const code = pre.querySelector("code");
      if (!code) return;
      try {
        await navigator.clipboard.writeText(code.textContent || "");
        button.textContent = "Copied ✓";
        window.setTimeout(() => {
          button.textContent = "Copy";
        }, 2000);
      } catch {
        button.textContent = "Copy failed";
        window.setTimeout(() => {
          button.textContent = "Copy";
        }, 2000);
      }
    });
    pre.appendChild(button);
  });
}

function buildToc() {
  const tocList = document.getElementById("toc-list");
  const tocMobileList = document.getElementById("toc-mobile-list");
  const headings = document.querySelectorAll("article.post-content h2");
  const links = [];

  headings.forEach((heading) => {
    if (!heading.id) heading.id = slugify(heading.textContent || "");
    const text = heading.textContent || "";
    [tocList, tocMobileList].forEach((target) => {
      if (!target) return;
      const li = document.createElement("li");
      const anchor = document.createElement("a");
      const span = document.createElement("span");
      anchor.href = `#${heading.id}`;
      anchor.dataset.target = heading.id;
      span.textContent = text;
      anchor.appendChild(span);
      li.appendChild(anchor);
      target.appendChild(li);
      links.push(anchor);
    });
  });

  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible?.target?.id) return;
      document.querySelectorAll("[data-target]").forEach((link) => {
        link.classList.toggle("is-active", link.dataset.target === visible.target.id);
      });
    },
    { rootMargin: "-20% 0px -65% 0px", threshold: [0.2, 0.6] }
  );

  headings.forEach((heading) => observer.observe(heading));
}

function updateReadRemaining() {
  const article = document.querySelector("article.post-content");
  const output = document.getElementById("read-remaining");
  if (!article || !output) return;

  const words = (article.textContent || "").trim().split(/\s+/).filter(Boolean);
  const totalWords = words.length;
  const rect = article.getBoundingClientRect();
  const articleHeight = Math.max(article.offsetHeight - window.innerHeight, 1);
  const distance = Math.min(Math.max(window.scrollY - (window.scrollY + rect.top), 0), articleHeight);
  const ratio = articleHeight <= 0 ? 0 : distance / articleHeight;
  const remainingWords = Math.max(0, Math.round(totalWords * (1 - ratio)));
  const remainingMinutes = Math.max(1, Math.ceil(remainingWords / WORDS_PER_MINUTE));
  output.textContent = `~${remainingMinutes} min remaining`;
}

function enableSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", (event) => {
      const href = anchor.getAttribute("href");
      if (!href || href === "#") return;
      const target = document.querySelector(href);
      if (!target) return;
      event.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function enableMobileTocToggle() {
  const button = document.getElementById("toc-toggle");
  const panel = document.getElementById("toc-mobile");
  if (!button || !panel) return;
  button.addEventListener("click", () => {
    panel.classList.toggle("is-open");
  });
}

document.addEventListener("DOMContentLoaded", () => {
  highlightCodeBlocks();
  addCopyButtons();
  buildToc();
  enableSmoothScroll();
  enableMobileTocToggle();
  updateProgressBar();
  updateReadRemaining();
  window.addEventListener("scroll", () => {
    updateProgressBar();
    updateReadRemaining();
  });
});
