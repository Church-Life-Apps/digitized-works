(() => {
  const storageKey = "digitized-works-theme";
  const choices = new Set(["system", "light", "dark"]);
  const systemDarkMode = window.matchMedia("(prefers-color-scheme: dark)");
  const themeColors = {light: "#f4f0e7", dark: "#111513"};

  function resolvedTheme(choice) {
    return choice === "system" ? (systemDarkMode.matches ? "dark" : "light") : choice;
  }

  function updateControls(choice) {
    document.querySelectorAll(".theme-button").forEach((button) => {
      const selected = button.dataset.theme === choice;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
  }

  function applyTheme(choice, persist = false) {
    const normalized = choices.has(choice) ? choice : "system";
    const appearance = resolvedTheme(normalized);
    document.documentElement.dataset.theme = appearance;
    document.documentElement.dataset.themeChoice = normalized;
    document.documentElement.style.colorScheme = appearance;
    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) themeColor.setAttribute("content", themeColors[appearance]);
    updateControls(normalized);
    if (persist) {
      try {
        localStorage.setItem(storageKey, normalized);
      } catch (error) {
        // Theme selection still works when storage is unavailable.
      }
    }
  }

  const linkedTheme = new URLSearchParams(window.location.search).get("theme");
  let savedTheme = linkedTheme || "system";
  try {
    savedTheme = linkedTheme || localStorage.getItem(storageKey) || "system";
  } catch (error) {
    // System is the safe default when storage is unavailable.
  }
  applyTheme(savedTheme);

  function bindThemeControls() {
    updateControls(document.documentElement.dataset.themeChoice || "system");
    document.querySelectorAll(".theme-button").forEach((button) => {
      button.addEventListener("click", () => applyTheme(button.dataset.theme, true));
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindThemeControls, {once: true});
  } else {
    bindThemeControls();
  }

  systemDarkMode.addEventListener("change", () => {
    if (document.documentElement.dataset.themeChoice === "system") applyTheme("system");
  });
})();
