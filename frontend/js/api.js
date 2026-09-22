// Base URL of the FastAPI backend. Change this if you deploy the backend elsewhere.
const API_BASE = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? "http://localhost:8000"
  : "";

const Api = {
  token() {
    return localStorage.getItem("access_token");
  },

  setToken(token) {
    localStorage.setItem("access_token", token);
  },

  clearToken() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_role");
  },

  isLoggedIn() {
    return !!this.token();
  },

  role() {
    return localStorage.getItem("user_role");
  },

  /**
   * Core request helper. Automatically attaches the bearer token and
   * parses JSON. Throws an Error with a readable message on failure.
   */
  async request(path, { method = "GET", body, isForm = false } = {}) {
    const headers = {};
    const token = this.token();
    if (token) headers["Authorization"] = `Bearer ${token}`;

    let payload = body;
    if (body && !isForm) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }

    const res = await fetch(`${API_BASE}${path}`, { method, headers, body: payload });

    if (res.status === 204) return null;

    let data;
    try {
      data = await res.json();
    } catch {
      data = null;
    }

    if (!res.ok) {
      const message = (data && (data.detail || data.message)) || `Request failed (${res.status})`;
      throw new Error(typeof message === "string" ? message : JSON.stringify(message));
    }
    return data;
  },

  get(path) {
    return this.request(path, { method: "GET" });
  },
  post(path, body) {
    return this.request(path, { method: "POST", body });
  },
  patch(path, body) {
    return this.request(path, { method: "PATCH", body });
  },
  del(path) {
    return this.request(path, { method: "DELETE" });
  },

  // Login uses OAuth2PasswordRequestForm (form-encoded, not JSON)
  async login(email, password) {
    const form = new URLSearchParams();
    form.append("username", email);
    form.append("password", password);
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Login failed");
    return data;
  },

  async uploadFile(path, file) {
    const form = new FormData();
    form.append("file", file);
    return this.request(path, { method: "POST", body: form, isForm: true });
  },
};

/** Redirects to login.html if no token is present. Call at the top of protected pages. */
function requireAuth() {
  if (!Api.isLoggedIn()) {
    window.location.href = "login.html";
  }
}

/** Redirects away if the logged-in user's role doesn't match. */
function requireRole(role) {
  requireAuth();
  if (Api.role() !== role) {
    window.location.href = "index.html";
  }
}

function logout() {
  Api.clearToken();
  window.location.href = "index.html";
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatDate(isoString) {
  if (!isoString) return "";
  const d = new Date(isoString);
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function formatSalary(min, max, currency) {
  if (!min && !max) return null;
  const fmt = (n) => `${currency || "USD"} ${Number(n).toLocaleString()}`;
  if (min && max) return `${fmt(min)} – ${fmt(max)}`;
  return fmt(min || max);
}

function jobTypeLabel(type) {
  const map = {
    full_time: "Full-time",
    part_time: "Part-time",
    contract: "Contract",
    internship: "Internship",
    remote: "Remote",
    freelance: "Freelance",
  };
  return map[type] || type;
}
