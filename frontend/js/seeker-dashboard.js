requireRole("job_seeker");
renderHeader("dashboard");

// ---------- Tab switching ----------
const tabs = document.querySelectorAll(".tab-btn");
const sections = {
  recommendations: document.getElementById("tab-recommendations"),
  assistant: document.getElementById("tab-assistant"),
  applications: document.getElementById("tab-applications"),
  profile: document.getElementById("tab-profile"),
  cvs: document.getElementById("tab-cvs"),
  notifications: document.getElementById("tab-notifications"),
};
const loaders = {
  recommendations: loadRecommendations,
  assistant: loadAssistant,
  applications: loadApplications,
  profile: loadProfile,
  cvs: loadCvs,
  notifications: loadNotifications,
};

tabs.forEach(btn => {
  btn.addEventListener("click", () => {
    tabs.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    Object.values(sections).forEach(s => s.style.display = "none");
    const tab = btn.dataset.tab;
    sections[tab].style.display = "block";
    loaders[tab]();
  });
});

// ---------- Recommendations ----------
async function loadRecommendations() {
  const el = sections.recommendations;
  el.innerHTML = `<p class="spinner-text">Finding matches based on your profile…</p>`;
  try {
    const jobs = await Api.get("/api/jobs/recommendations/me");
    if (!jobs.length) {
      el.innerHTML = `<div class="empty-state">
        <h3>No recommendations yet</h3>
        <p>Fill out your profile and add skills, then refresh your embedding from the Profile tab — recommendations are based on that.</p>
      </div>`;
      return;
    }
    el.innerHTML = jobs.map(job => `
      <a class="job-card" href="job-detail.html?id=${job.id}">
        <div class="card-title-row">
          <div>
            <div class="job-title">${escapeHtml(job.title)}</div>
            <div class="job-company">${escapeHtml(job.company_name || "")}</div>
          </div>
          ${job.similarity_score != null ? `<span class="match-badge">${Math.round(job.similarity_score * 100)}% match</span>` : ""}
        </div>
        <div class="job-meta">
          <span>${escapeHtml(job.location || (job.is_remote ? "Remote" : ""))}</span>
          <span>${jobTypeLabel(job.job_type)}</span>
        </div>
      </a>
    `).join("");
  } catch (err) {
    el.innerHTML = `<div class="alert alert-error">${escapeHtml(err.message)}</div>`;
  }
}

// ---------- Applications ----------
async function loadApplications() {
  const el = sections.applications;
  el.innerHTML = `<p class="spinner-text">Loading…</p>`;
  try {
    const apps = await Api.get("/api/applications/me");
    if (!apps.length) {
      el.innerHTML = `<div class="empty-state"><h3>No applications yet</h3><p>Browse jobs and apply to see them tracked here.</p></div>`;
      return;
    }
    el.innerHTML = `
      <table>
        <thead><tr><th>Job</th><th>Status</th><th>Match score</th><th>Applied</th></tr></thead>
        <tbody>
          ${apps.map(a => `
            <tr>
              <td><a href="job-detail.html?id=${a.job_id}">View job</a></td>
              <td><span class="pill pill-${a.status}">${a.status}</span></td>
              <td>${a.match_score != null ? Math.round(a.match_score) + "%" : "—"}</td>
              <td>${formatDate(a.applied_at)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  } catch (err) {
    el.innerHTML = `<div class="alert alert-error">${escapeHtml(err.message)}</div>`;
  }
}

// ---------- Profile ----------
async function loadProfile() {
  const el = sections.profile;
  el.innerHTML = `<p class="spinner-text">Loading…</p>`;
  try {
    const profile = await Api.get("/api/job-seekers/me");
    el.innerHTML = `
      <div class="card">
        <div id="profile-alert"></div>
        <form id="profile-form">
          <div class="field-row">
            <div>
              <label for="full_name">Full name</label>
              <input id="full_name" value="${escapeHtml(profile.full_name || "")}">
            </div>
            <div>
              <label for="phone">Phone</label>
              <input id="phone" value="${escapeHtml(profile.phone || "")}">
            </div>
          </div>
          <div class="field-row">
            <div>
              <label for="location">Location</label>
              <input id="location" value="${escapeHtml(profile.location || "")}">
            </div>
            <div>
              <label for="experience_years">Years of experience</label>
              <input id="experience_years" type="number" step="0.5" value="${profile.experience_years ?? ""}">
            </div>
          </div>
          <label for="headline">Headline</label>
          <input id="headline" placeholder="e.g. Senior Backend Engineer" value="${escapeHtml(profile.headline || "")}">

          <label for="summary">Summary</label>
          <textarea id="summary">${escapeHtml(profile.summary || "")}</textarea>

          <label for="linkedin_url">LinkedIn URL</label>
          <input id="linkedin_url" value="${escapeHtml(profile.linkedin_url || "")}">

          <div style="display:flex; gap:10px; margin-top:20px;">
            <button type="submit" class="btn btn-primary">Save changes</button>
          </div>
        </form>
      </div>

      <div class="card">
        <h3>Skills</h3>
        <p class="muted">Add skills so job matching and recommendations understand what you offer.</p>
        <div id="skills-list" class="tag-list"></div>
        <div style="display:flex; gap:8px; margin-top:12px;">
          <input id="new-skill" placeholder="e.g. Python" style="max-width:220px;">
          <button class="btn btn-secondary" id="add-skill-btn">Add skill</button>
        </div>
      </div>

      <div class="card">
        <h3>Recommendation embedding</h3>
        <p class="muted">Recommendations are computed from your headline, summary, and skills. Refresh after editing any of those.</p>
        <button class="btn btn-secondary" id="refresh-embedding-btn">Refresh recommendations embedding</button>
        <div id="embedding-alert" style="margin-top:12px;"></div>
      </div>
    `;

    loadSkillsList();

    document.getElementById("profile-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const alertBox = document.getElementById("profile-alert");
      try {
        await Api.patch("/api/job-seekers/me", {
          full_name: document.getElementById("full_name").value.trim(),
          phone: document.getElementById("phone").value.trim() || null,
          location: document.getElementById("location").value.trim() || null,
          experience_years: document.getElementById("experience_years").value ? Number(document.getElementById("experience_years").value) : null,
          headline: document.getElementById("headline").value.trim() || null,
          summary: document.getElementById("summary").value.trim() || null,
          linkedin_url: document.getElementById("linkedin_url").value.trim() || null,
        });
        alertBox.innerHTML = `<div class="alert alert-success">Profile saved.</div>`;
      } catch (err) {
        alertBox.innerHTML = `<div class="alert alert-error">${escapeHtml(err.message)}</div>`;
      }
    });

    document.getElementById("add-skill-btn").addEventListener("click", async () => {
      const input = document.getElementById("new-skill");
      const name = input.value.trim();
      if (!name) return;
      try {
        await Api.post("/api/job-seekers/me/skills", { skill_name: name, proficiency: "intermediate" });
        input.value = "";
        loadSkillsList();
      } catch (err) {
        alert(err.message);
      }
    });

    document.getElementById("refresh-embedding-btn").addEventListener("click", async () => {
      const alertBox = document.getElementById("embedding-alert");
      try {
        await Api.post("/api/job-seekers/me/refresh-embedding");
        alertBox.innerHTML = `<div class="alert alert-success">Embedding refreshed — your recommendations tab now reflects your latest profile.</div>`;
      } catch (err) {
        alertBox.innerHTML = `<div class="alert alert-error">${escapeHtml(err.message)}</div>`;
      }
    });
  } catch (err) {
    el.innerHTML = `<div class="alert alert-error">${escapeHtml(err.message)}</div>`;
  }
}

async function loadSkillsList() {
  const el = document.getElementById("skills-list");
  try {
    const skills = await Api.get("/api/job-seekers/me/skills");
    if (!skills.length) {
      el.innerHTML = `<span class="muted" style="font-size:0.85rem;">No skills added yet.</span>`;
      return;
    }
    el.innerHTML = skills.map(s => `
      <span class="tag">
        ${escapeHtml(s.skill_name)}
        <button class="remove-skill-btn" data-id="${s.skill_id}" style="background:none;border:none;cursor:pointer;color:inherit;margin-left:4px;font-weight:700;">×</button>
      </span>
    `).join("");
    document.querySelectorAll(".remove-skill-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        await Api.del(`/api/job-seekers/me/skills/${btn.dataset.id}`);
        loadSkillsList();
      });
    });
  } catch (err) {
    el.innerHTML = `<span class="muted" style="font-size:0.85rem;">Could not load skills.</span>`;
  }
}

// ---------- CVs ----------
async function loadCvs() {
  const el = sections.cvs;
  el.innerHTML = `<p class="spinner-text">Loading…</p>`;
  try {
    const cvs = await Api.get("/api/cvs/me");
    el.innerHTML = `
      <div class="card">
        <h3>Upload a CV</h3>
        <p class="muted">PDF or DOCX, up to 5MB. We'll parse it, detect skills, and generate a short summary automatically.</p>
        <input type="file" id="cv-file" accept=".pdf,.docx">
        <button class="btn btn-primary" id="upload-cv-btn" style="margin-top:12px;">Upload</button>
        <div id="upload-alert" style="margin-top:12px;"></div>
      </div>
      <div id="cv-list">
        ${cvs.length ? cvs.map(cv => `
          <div class="card flex-between">
            <div>
              <strong>${escapeHtml(cv.file_name)}</strong>
              ${cv.is_primary ? `<span class="pill pill-open" style="margin-left:8px;">Primary</span>` : ""}
              <div class="muted" style="font-size:0.85rem;">Uploaded ${formatDate(cv.uploaded_at)}</div>
            </div>
            <div style="display:flex; gap:8px;">
              ${!cv.is_primary ? `<button class="btn btn-secondary set-primary-btn" data-id="${cv.id}">Make primary</button>` : ""}
              <button class="btn btn-danger delete-cv-btn" data-id="${cv.id}">Delete</button>
            </div>
          </div>
        `).join("") : `<div class="empty-state"><h3>No CVs uploaded</h3></div>`}
      </div>
    `;

    document.getElementById("upload-cv-btn").addEventListener("click", async () => {
      const fileInput = document.getElementById("cv-file");
      const alertBox = document.getElementById("upload-alert");
      if (!fileInput.files.length) return;
      try {
        const result = await Api.uploadFile("/api/cvs/upload", fileInput.files[0]);
        alertBox.innerHTML = `<div class="alert alert-success">
          Uploaded. Detected skills: ${result.detected_skills.length ? escapeHtml(result.detected_skills.join(", ")) : "none found"}.
        </div>`;
        loadCvs();
      } catch (err) {
        alertBox.innerHTML = `<div class="alert alert-error">${escapeHtml(err.message)}</div>`;
      }
    });

    document.querySelectorAll(".set-primary-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        await Api.patch(`/api/cvs/${btn.dataset.id}/set-primary`);
        loadCvs();
      });
    });

    document.querySelectorAll(".delete-cv-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        if (!confirm("Delete this CV?")) return;
        await Api.del(`/api/cvs/${btn.dataset.id}`);
        loadCvs();
      });
    });
  } catch (err) {
    el.innerHTML = `<div class="alert alert-error">${escapeHtml(err.message)}</div>`;
  }
}

// ---------- Notifications ----------
async function loadNotifications() {
  const el = sections.notifications;
  el.innerHTML = `<p class="spinner-text">Loading…</p>`;
  try {
    const notifs = await Api.get("/api/notifications");
    if (!notifs.length) {
      el.innerHTML = `<div class="empty-state"><h3>No notifications</h3></div>`;
      return;
    }
    el.innerHTML = `
      <div class="flex-between" style="margin-bottom:12px;">
        <span class="muted">${notifs.filter(n => !n.is_read).length} unread</span>
        <button class="btn btn-secondary" id="mark-all-btn">Mark all as read</button>
      </div>
      ${notifs.map(n => `
        <div class="card" style="${n.is_read ? "opacity:0.65;" : ""}">
          <div class="flex-between">
            <strong>${escapeHtml(n.title)}</strong>
            <span class="muted" style="font-size:0.8rem;">${formatDate(n.created_at)}</span>
          </div>
          <p style="margin-top:6px;">${escapeHtml(n.message)}</p>
        </div>
      `).join("")}
    `;
    document.getElementById("mark-all-btn").addEventListener("click", async () => {
      await Api.patch("/api/notifications/read-all");
      loadNotifications();
    });
  } catch (err) {
    el.innerHTML = `<div class="alert alert-error">${escapeHtml(err.message)}</div>`;
  }
}

// ---------- AI Assistant ----------
let assistantLoaded = false;

async function loadAssistant() {
  const el = sections.assistant;
  if (assistantLoaded) return;
  assistantLoaded = true;

  el.innerHTML = `
    <div class="card">
      <p class="muted" style="margin-top:0;">
        Try: "Find me five suitable Java developer jobs.", "Which of these jobs am I most qualified for?",
        "What skills am I missing?", "Draft an application for the second job.", or
        "Search again and exclude jobs requiring more than two years' experience."
      </p>
      <div id="chat-log" class="stack" style="max-height:480px; overflow-y:auto; margin-bottom:16px;"></div>
      <div style="display:flex; gap:8px;">
        <input type="text" id="chat-input" placeholder="Ask about jobs, skills, or applications…" style="flex:1;">
        <button class="btn btn-primary" id="chat-send-btn">Send</button>
      </div>
    </div>
  `;

  await loadChatHistory();

  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send-btn");

  const send = async () => {
    const message = input.value.trim();
    if (!message) return;
    input.value = "";
    appendChatBubble("user", message);
    sendBtn.disabled = true;

    const thinkingId = appendChatBubble("assistant", "…");
    try {
      const result = await Api.post("/api/assistant/chat", { message });
      updateChatBubble(thinkingId, result);
    } catch (err) {
      updateChatBubble(thinkingId, { reply: `Sorry, something went wrong: ${err.message}` });
    }
    sendBtn.disabled = false;
    input.focus();
  };

  sendBtn.addEventListener("click", send);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });
}

async function loadChatHistory() {
  try {
    const history = await Api.get("/api/assistant/history");
    history.forEach(m => appendChatBubble(m.role, m.content));
  } catch (err) {
    // fine to start with an empty conversation if history can't load
  }
}

let chatBubbleCounter = 0;

function appendChatBubble(role, content) {
  const log = document.getElementById("chat-log");
  const id = `chat-bubble-${chatBubbleCounter++}`;
  const isUser = role === "user";
  const bubble = document.createElement("div");
  bubble.id = id;
  bubble.style.cssText = `
    max-width: 80%;
    align-self: ${isUser ? "flex-end" : "flex-start"};
    background: ${isUser ? "var(--teal-tint)" : "var(--paper)"};
    border: 1px solid ${isUser ? "var(--teal)" : "var(--line)"};
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 0.92rem;
  `;
  bubble.innerHTML = `<div>${escapeHtml(content)}</div>`;
  log.style.display = "flex";
  log.style.flexDirection = "column";
  log.appendChild(bubble);
  log.scrollTop = log.scrollHeight;
  return id;
}

function updateChatBubble(id, result) {
  const bubble = document.getElementById(id);
  if (!bubble) return;

  let html = `<div>${escapeHtml(result.reply || "")}</div>`;

  if (result.jobs && result.jobs.length) {
    html += `<div class="stack" style="margin-top:10px;">` + result.jobs.map(j => `
      <a class="job-card" href="job-detail.html?id=${j.id}" style="padding:12px 14px; margin-bottom:0;">
        <div class="card-title-row">
          <div>
            <div class="job-title" style="font-size:0.95rem;">${escapeHtml(j.title)}</div>
            <div class="job-company" style="font-size:0.82rem;">${escapeHtml(j.company_name)}</div>
          </div>
          ${j.match_score != null ? `<span class="match-badge">${Math.round(j.match_score)}% match</span>` : ""}
        </div>
      </a>
    `).join("") + `</div>`;
  }

  if (result.missing_skills) {
    const req = result.missing_skills.required || [];
    const pref = result.missing_skills.preferred || [];
    if (req.length || pref.length) {
      html += `<div style="margin-top:10px;">`;
      if (req.length) html += `<div class="tag-list">${req.map(s => `<span class="tag">${escapeHtml(s)}</span>`).join("")}</div>`;
      if (pref.length) html += `<div class="tag-list" style="margin-top:4px;">${pref.map(s => `<span class="tag" style="opacity:0.7;">${escapeHtml(s)} (preferred)</span>`).join("")}</div>`;
      html += `</div>`;
    }
  }

  if (result.cover_letter) {
    html += `<div class="card" style="margin-top:10px; margin-bottom:0; white-space:pre-wrap; font-size:0.88rem;">${escapeHtml(result.cover_letter)}</div>`;
  }

  bubble.innerHTML = html;
  const log = document.getElementById("chat-log");
  if (log) log.scrollTop = log.scrollHeight;
}

// initial load
loadRecommendations();
