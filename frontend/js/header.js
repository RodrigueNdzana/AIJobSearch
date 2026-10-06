// Theme management
function initTheme() {
  const savedTheme = localStorage.getItem("theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  
  if (savedTheme) {
    document.documentElement.setAttribute("data-theme", savedTheme);
  } else if (prefersDark) {
    document.documentElement.setAttribute("data-theme", "dark");
  }
}

function setTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("theme", theme);
  updateThemeToggle(theme);
}

function updateThemeToggle(currentTheme) {
  const lightBtn = document.getElementById("theme-light");
  const darkBtn = document.getElementById("theme-dark");
  
  if (lightBtn && darkBtn) {
    lightBtn.classList.toggle("active", currentTheme === "light");
    darkBtn.classList.toggle("active", currentTheme === "dark");
  }
}

function renderHeader(activePage) {
  const loggedIn = Api.isLoggedIn();
  const role = Api.role();

  let links = `<a href="index.html" class="${activePage === "browse" ? "active" : ""}">Browse jobs</a>`;

  if (loggedIn && role === "job_seeker") {
    links += `<a href="seeker-dashboard.html" class="${activePage === "dashboard" ? "active" : ""}">My dashboard</a>`;
  } else if (loggedIn && role === "employer") {
    links += `<a href="employer-dashboard.html" class="${activePage === "dashboard" ? "active" : ""}">My dashboard</a>`;
  }

  if (loggedIn) {
    links += `<a href="#" id="logout-link">Log out</a>`;
  } else {
    links += `<a href="login.html" class="${activePage === "login" ? "active" : ""}">Log in</a>`;
    links += `<a href="register.html" class="btn btn-primary">Sign up</a>`;
  }

  const currentTheme = document.documentElement.getAttribute("data-theme") || "light";

  document.getElementById("site-header").innerHTML = `
    <div class="wrap">
      <a href="index.html" class="brand"><span class="mark">AI</span> Jobline</a>
      <nav class="nav-links">
        ${links}
        <div class="theme-toggle">
          <button class="theme-toggle-btn ${currentTheme === "light" ? "active" : ""}" id="theme-light" aria-label="Light mode">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          </button>
          <button class="theme-toggle-btn ${currentTheme === "dark" ? "active" : ""}" id="theme-dark" aria-label="Dark mode">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
          </button>
        </div>
        <button class="mobile-menu-btn" id="mobile-menu-toggle" aria-label="Toggle menu">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      </nav>
    </div>
  `;

  // Theme toggle handlers
  const lightBtn = document.getElementById("theme-light");
  const darkBtn = document.getElementById("theme-dark");
  
  if (lightBtn) {
    lightBtn.addEventListener("click", () => setTheme("light"));
  }
  
  if (darkBtn) {
    darkBtn.addEventListener("click", () => setTheme("dark"));
  }

  // Mobile menu toggle
  const mobileMenuToggle = document.getElementById("mobile-menu-toggle");
  const navLinks = document.querySelector(".nav-links");
  
  if (mobileMenuToggle && navLinks) {
    mobileMenuToggle.addEventListener("click", () => {
      navLinks.classList.toggle("active");
    });
  }

  // Logout handler
  const logoutLink = document.getElementById("logout-link");
  if (logoutLink) {
    logoutLink.addEventListener("click", (e) => {
      e.preventDefault();
      logout();
    });
  }
}

// Initialize theme on page load
initTheme();
