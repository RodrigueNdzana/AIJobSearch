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
    links += `<a href="register.html" class="btn btn-primary" style="padding:6px 14px;">Sign up</a>`;
  }

  document.getElementById("site-header").innerHTML = `
    <div class="wrap">
      <a href="index.html" class="brand"><span class="mark">AI</span> Jobline</a>
      <nav class="nav-links">${links}</nav>
    </div>
  `;

  const logoutLink = document.getElementById("logout-link");
  if (logoutLink) {
    logoutLink.addEventListener("click", (e) => {
      e.preventDefault();
      logout();
    });
  }
}
