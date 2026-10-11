/**
 * TruthLens AI — Main Client-side Script (Stage 1 Redesign)
 * Handles Light/Dark Theme persistence, Tab Navigation, and Form UX.
 */

document.addEventListener("DOMContentLoaded", () => {
  // --- 1. Theme Persistence (Light by default, Dark toggle) ---
  const themeToggleBtn = document.getElementById("theme-toggle-btn");
  const themeIcon = document.getElementById("theme-icon");
  const themeText = document.getElementById("theme-text");

  function applyTheme(theme) {
    if (theme === "dark") {
      document.documentElement.setAttribute("data-theme", "dark");
      if (themeIcon) themeIcon.textContent = "☀️";
      if (themeText) themeText.textContent = "Light Mode";
    } else {
      document.documentElement.removeAttribute("data-theme");
      if (themeIcon) themeIcon.textContent = "🌙";
      if (themeText) themeText.textContent = "Dark Mode";
    }
  }

  // Check saved preference or default to light
  const savedTheme = localStorage.getItem("truthlens_theme") || "light";
  applyTheme(savedTheme);

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener("click", () => {
      const currentTheme = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
      const newTheme = currentTheme === "dark" ? "light" : "dark";
      localStorage.setItem("truthlens_theme", newTheme);
      applyTheme(newTheme);
    });
  }

  // --- 2. Tab Navigation ---
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");
  const activeTabInput = document.getElementById("active_tab_input");

  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.classList.contains("disabled")) return;

      const targetTab = btn.getAttribute("data-tab");
      
      tabBtns.forEach((b) => b.classList.remove("active"));
      tabPanes.forEach((p) => p.classList.remove("active"));

      btn.classList.add("active");
      const activePane = document.getElementById(`tab-${targetTab}`);
      if (activePane) activePane.classList.add("active");

      if (activeTabInput) activeTabInput.value = targetTab;
    });
  });

  // --- 3. Text Area Counters ---
  const textarea = document.getElementById("news_text");
  const charCounter = document.getElementById("char-counter");
  const wordCounter = document.getElementById("word-counter");
  const clearBtn = document.getElementById("clear-btn");

  function updateCounters() {
    if (!textarea) return;
    const text = textarea.value || "";
    const charCount = text.length;
    const words = text.trim() ? text.trim().split(/\s+/).length : 0;

    if (charCounter) {
      charCounter.textContent = `${charCount.toLocaleString()} / 15,000 characters`;
      charCounter.style.color = charCount > 15000 ? "var(--misleading-color)" : "";
    }

    if (wordCounter) {
      wordCounter.textContent = `${words.toLocaleString()} words`;
    }
  }

  if (textarea) {
    textarea.addEventListener("input", updateCounters);
    updateCounters();
  }

  if (clearBtn && textarea) {
    clearBtn.addEventListener("click", () => {
      textarea.value = "";
      textarea.focus();
      updateCounters();
    });
  }

  // --- 4. Demonstration Loaders ---
  const demoButtons = document.querySelectorAll(".demo-btn");
  demoButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const demoText = btn.getAttribute("data-text");
      if (demoText && textarea) {
        // Switch to text tab if needed
        const textTabBtn = document.querySelector('.tab-btn[data-tab="text"]');
        if (textTabBtn) textTabBtn.click();

        textarea.value = demoText;
        updateCounters();
        textarea.scrollIntoView({ behavior: "smooth", block: "center" });
        textarea.focus();
      }
    });
  });

  // --- 5. Form Submission Loading Spinners ---
  const forms = document.querySelectorAll("form.analyzing-form");
  forms.forEach((form) => {
    form.addEventListener("submit", () => {
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = `
          <svg class="spinner" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 1s linear infinite;">
            <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
            <path d="M12 2a10 10 0 0 1 10 10"></path>
          </svg>
          Analyzing...
        `;
      }
    });
  });

  // --- 6. Live News Feed Event Handlers & Dynamic Refresh ---
  document.addEventListener("click", (e) => {
    const analyzeBtn = e.target.closest(".feed-analyze-btn");
    if (analyzeBtn) {
      const targetUrl = analyzeBtn.getAttribute("data-url");
      if (targetUrl) {
        const urlTabBtn = document.querySelector('.tab-btn[data-tab="url"]');
        if (urlTabBtn) urlTabBtn.click();

        const urlInput = document.getElementById("article_url");
        if (urlInput) {
          urlInput.value = targetUrl;
          urlInput.scrollIntoView({ behavior: "smooth", block: "center" });
          urlInput.focus();
        }
      }
    }
  });

  const refreshFeedBtn = document.getElementById("btn-refresh-feed");
  const feedContentArea = document.getElementById("news-feed-content-area");
  const feedUpdatedLabel = document.getElementById("feed-updated-label");

  function escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function renderFeedArticles(articles) {
    if (!articles || articles.length === 0) {
      return `
        <div id="news-feed-empty-box" class="alert-box alert-info" style="margin-top: 0.5rem;">
          <span style="font-size: 1.2rem;">ℹ️</span>
          <div>
            <strong>No Articles Found:</strong>
            <div>No recent articles returned by feed query.</div>
            <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">
              Try clicking Refresh again in a few moments.
            </div>
          </div>
        </div>
      `;
    }

    const cardsHtml = articles
      .map(
        (article) => `
        <div class="feed-item-card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; font-size: 0.78rem;">
            <span class="feed-domain-badge">${escapeHtml(article.source_domain)}</span>
            <span style="color: var(--text-muted);" title="Article Publication Date">Published: ${escapeHtml(article.seendate_formatted)}</span>
          </div>
          <h4 class="feed-article-title">
            <a href="${escapeHtml(article.url)}" target="_blank" rel="noopener noreferrer">
              ${escapeHtml(article.title)} ↗
            </a>
          </h4>
          <div style="margin-top: 0.75rem; display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(article.source_country)}</span>
            <button type="button" class="feed-analyze-btn" data-url="${escapeHtml(article.url)}">
              ⚡ Analyze
            </button>
          </div>
        </div>
      `
      )
      .join("");

    return `<div class="news-feed-grid" id="news-feed-container">${cardsHtml}</div>`;
  }

  function renderFeedError(notice, message) {
    return `
      <div id="news-feed-error-box" class="alert-box alert-amber" style="margin-top: 0.5rem;">
        <span style="font-size: 1.2rem;">⚠️</span>
        <div>
          <strong>Live News Feed Notice:</strong>
          <div>${escapeHtml(notice || "Live news feed temporarily unavailable.")}</div>
          <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">
            ${escapeHtml(message || "Could not retrieve articles from GDELT API.")}
          </div>
        </div>
      </div>
    `;
  }

  if (refreshFeedBtn) {
    let cooldownTimer = null;

    function startCooldown(seconds) {
      let remaining = seconds;
      refreshFeedBtn.disabled = true;
      refreshFeedBtn.textContent = `⏳ Wait (${remaining}s)...`;

      if (cooldownTimer) clearInterval(cooldownTimer);
      cooldownTimer = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
          clearInterval(cooldownTimer);
          cooldownTimer = null;
          refreshFeedBtn.disabled = false;
          refreshFeedBtn.textContent = "🔄 Refresh";
        } else {
          refreshFeedBtn.textContent = `⏳ Wait (${remaining}s)...`;
        }
      }, 1000);
    }

    refreshFeedBtn.addEventListener("click", async () => {
      if (refreshFeedBtn.disabled) return;
      refreshFeedBtn.disabled = true;
      refreshFeedBtn.textContent = "⏳ Refreshing...";

      if (feedContentArea) {
        feedContentArea.innerHTML = `
          <div class="alert-box alert-info" style="margin-top: 0.5rem; justify-content: center; align-items: center; gap: 0.75rem; padding: 1.5rem;">
            <svg class="spinner" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 1s linear infinite;">
              <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
              <path d="M12 2a10 10 0 0 1 10 10"></path>
            </svg>
            <span style="font-size: 0.88rem; color: var(--text-secondary);">Contacting GDELT Project for latest news dispatches...</span>
          </div>
        `;
      }

      try {
        const res = await fetch("/api/news-feed?refresh=true");
        const data = await res.json();

        if (data && data.last_updated && feedUpdatedLabel) {
          feedUpdatedLabel.textContent = `Feed Retrieved: ${data.last_updated}${data.is_cached && !data.last_updated.includes("cached") ? " (cached)" : ""}`;
        }

        if (data && data.status === "success") {
          if (feedContentArea) {
            feedContentArea.innerHTML = renderFeedArticles(data.articles);
          }
        } else {
          if (feedContentArea) {
            feedContentArea.innerHTML = renderFeedError(data.notice, data.message);
          }
        }
      } catch (err) {
        if (feedContentArea) {
          feedContentArea.innerHTML = renderFeedError(
            "Connection error",
            "Could not reach TruthLens news feed service."
          );
        }
      } finally {
        startCooldown(10);
      }
    });
  }

});

// Inline spin animation
const style = document.createElement("style");
style.textContent = `
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
`;
document.head.appendChild(style);

