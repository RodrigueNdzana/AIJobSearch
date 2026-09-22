requireRole("employer");
renderHeader("dashboard");

const tabs = document.querySelectorAll(".tab-btn");
const sections = {
  jobs: document.getElementById("tab-jobs"),
  post: document.getElementById("tab-post"),
  company: document.getElementById("tab-company"),
  notifications: document.getElementById("tab-notifications"),
};
const loaders = {
  jobs: loadMyJobs,
  post: renderPostForm,
  company: loadCompanyProfile,
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

// ---------- My job postings ----------
async function loadMyJobs() {
  const el = sections.jobs;
  el.innerHTML = `<p class="spinner-text">Loading…</p>`;
  try {
    const jobs = await Api.get("/api/jobs/employer/me");
    if (!jobs.length) {
      el.innerHTML = `<div class="empty-state"><h3>No jobs posted yet</h3><p>Use the "Post a job" tab to create your first listing.</p></div>`;
      return;
    }
    el.innerHTML = jobs.map(job => `
      <div class="card">
        <div class="card-title-row">
          <div>
            <div class="job-title">${escapeHtml(job.title)}</div>
            <div class="job-meta" style="margin-top:6px;">
              <span>${escapeHtml(job.location || (job.is_remote ? "Remote" : ""))}</span>
              <span>${jobTypeLabel(job.job_type)}</span>
              <span>${job.views_count} views</span>
            </div>
          </div>
          <span class="pill pill-${job.status}">${job.status}</span>
        </div>
        <div style="display:flex; gap:8px; margin-top:16px;">
          <button class="btn btn-secondary view-applicants-btn" data-id="${job.id}" data-title="${escapeHtml(job.title)}">View applicants</button>
          ${job.status === "open"
            ? `<button class="btn btn-secondary close-job-btn" data-id="${job.id}">Close posting</button>`
            : job.status === "draft"
              ? `<button class="btn btn-primary publish-job-btn" data-id="${job.id}">Publish</button>`
              : ""}
        </div>
      </div>
    `).join("");

    document.querySelectorAll(".view-applicants-btn").forEach(btn => {
      btn.addEventListener("click", () => openApplicantsModal(btn.dataset.id, btn.dataset.title));
    });
    document.querySelectorAll(".close-job-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        await Api.patch(`/api/jobs/${btn.dataset.id}`, { status: "closed" });
        loadMyJobs();
      });
    });
    document.querySelectorAll(".publish-job-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        await Api.patch(`/api/jobs/${btn.dataset.id}`, { status: "open" });
        loadMyJobs();
      });
    });
  } catch (err) {
    el.innerHTML = `<div class="alert alert-error">${escapeHtml(err.message)}</div>`;
  }
}

// ---------- Applicants modal ----------
const modal = document.getElementById("applicants-modal");
document.getElementById("close-modal-btn").addEventListener("click", () => modal.style.display = "none");

async function openApplicantsModal(jobId, jobTitle) {
  document.getElementById("applicants-title").textContent = `Applicants — ${jobTitle}`;
  const contentEl = document.getElementById("applicants-content");
  contentEl.innerHTML = `<p class="spinner-text">Loading…</p>`;
  modal.style.display = "block";

  try {
    const apps = await Api.get(`/api/applications/job/${jobId}`);
    if (!apps.length) {
      contentEl.innerHTML = `<div class="empty-state"><h3>No applicants yet</h3></div>`;
      return;
    }
    // sorted server-side by match_score desc already
    contentEl.innerHTML = apps.map(a => `
      <div class="card">
        <div class="flex-between">
          <div>
            <strong>Applicant</strong>
            <div class="muted" style="font-size:0.85rem;">Applied ${formatDate(a.applied_at)}</div>
          </div>
          <div style="text-align:right;">
            ${a.match_score != null ? `<div class="match-badge">${Math.round(a.match_score)}% match</div>` : ""}
          </div>
        </div>
        ${a.cover_letter ? `<p style="margin-top:10px; white-space:pre-wrap;">${escapeHtml(a.cover_letter)}</p>` : ""}
        <div class="flex-between" style="margin-top:12px;">
          <span class="pill pill-${a.status}">${a.status}</span>
          <select class="status-select" data-id="${a.id}" style="width:auto;">
            <option value="pending" ${a.status === "pending" ? "selected" : ""}>Pending</option>
            <option value="reviewed" ${a.status === "reviewed" ? "selected" : ""}>Reviewed</option>
            <option value="shortlisted" ${a.status === "shortlisted" ? "selected" : ""}>Shortlisted</option>
            <option value="interview" ${a.status === "interview" ? "selected" : ""}>Interview</option>
            <option value="hired" ${a.status === "hired" ? "selected" : ""}>Hired</option>
            <option value="rejected" ${a.status === "rejected" ? "selected" : ""}>Rejected</option>
          </select>
        </div>
      </div>
    `).join("");

    document.querySelectorAll(".status-select").forEach(sel => {
      sel.addEventListener("change", async () => {
        try {
          await Api.patch(`/api/applications/${sel.dataset.id}/status`, { status: sel.value });
        } catch (err) {
          alert(err.message);
        }
      });
    });
  } catch (err) {
    contentEl.innerHTML = `<div class="alert alert-error">${escapeHtml(err.message)}</div>`;
  }
}

// ---------- Post a job ----------
function renderPostForm() {
  const el = sections.post;
  el.innerHTML = `
    <div class="card">
      <div id="post-alert"></div>
      <form id="post-job-form">
        <label for="title">Job title</label>
        <input id="title" required placeholder="e.g. Senior Backend Engineer">

        <label for="description">Description</label>
        <textarea id="description" required placeholder="Role overview, what the team does, day-to-day..."></textarea>

        <label for="requirements">Requirements</label>
        <textarea id="requirements" placeholder="Must-haves for this role"></textarea>

        <div class="field-row">
          <div>
            <label for="location">Location</label>
            <input id="location" placeholder="e.g. Cape Town">
          </div>
          <div>
            <label for="job_type">Job type</label>
            <select id="job_type">
              <option value="full_time">Full-time</option>
              <option value="part_time">Part-time</option>
              <option value="contract">Contract</option>
              <option value="internship">Internship</option>
              <option value="freelance">Freelance</option>
            </select>
          </div>
        </div>

        <div class="field-row">
          <div>
            <label for="salary_min">Salary min</label>
            <input id="salary_min" type="number">
          </div>
          <div>
            <label for="salary_max">Salary max</label>
            <input id="salary_max" type="number">
          </div>
        </div>

        <label><input type="checkbox" id="is_remote" style="width:auto; display:inline-block; margin-right:6px;"> Remote position</label>

        <label for="required_skills">Required skills (comma-separated)</label>
        <input id="required_skills" placeholder="e.g. Python, FastAPI, PostgreSQL">

        <label for="preferred_skills">Preferred skills (comma-separated, optional)</label>
        <input id="preferred_skills" placeholder="e.g. Docker, AWS">

        <button type="submit" class="btn btn-primary" style="margin-top:20px;">Publish job</button>
      </form>
    </div>
  `;

  document.getElementById("post-job-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const alertBox = document.getElementById("post-alert");
    const splitSkills = (v) => v.split(",").map(s => s.trim()).filter(Boolean);

    try {
      const payload = {
        title: document.getElementById("title").value.trim(),
        description: document.getElementById("description").value.trim(),
        requirements: document.getElementById("requirements").value.trim() || null,
        location: document.getElementById("location").value.trim() || null,
        job_type: document.getElementById("job_type").value,
        is_remote: document.getElementById("is_remote").checked,
        salary_min: document.getElementById("salary_min").value ? Number(document.getElementById("salary_min").value) : null,
        salary_max: document.getElementById("salary_max").value ? Number(document.getElementById("salary_max").value) : null,
        required_skills: splitSkills(document.getElementById("required_skills").value),
        preferred_skills: splitSkills(document.getElementById("preferred_skills").value),
      };
      const job = await Api.post("/api/jobs", payload);
      alertBox.innerHTML = `<div class="alert alert-success">Job posted. <a href="job-detail.html?id=${job.id}">View listing</a></div>`;
      document.getElementById("post-job-form").reset();
    } catch (err) {
      alertBox.innerHTML = `<div class="alert alert-error">${escapeHtml(err.message)}</div>`;
    }
  });
}

// ---------- Company profile ----------
async function loadCompanyProfile() {
  const el = sections.company;
  el.innerHTML = `<p class="spinner-text">Loading…</p>`;
  try {
    const company = await Api.get("/api/employers/me");
    el.innerHTML = `
      <div class="card">
        <div id="company-alert"></div>
        <form id="company-form">
          <label for="company_name">Company name</label>
          <input id="company_name" value="${escapeHtml(company.company_name || "")}">

          <label for="industry">Industry</label>
          <input id="industry" value="${escapeHtml(company.industry || "")}">

          <label for="company_size">Company size</label>
          <input id="company_size" placeholder="e.g. 51-200" value="${escapeHtml(company.company_size || "")}">

          <label for="website_url">Website</label>
          <input id="website_url" value="${escapeHtml(company.website_url || "")}">

          <label for="location">Location</label>
          <input id="location" value="${escapeHtml(company.location || "")}">

          <label for="company_description">About the company</label>
          <textarea id="company_description">${escapeHtml(company.company_description || "")}</textarea>

          <button type="submit" class="btn btn-primary" style="margin-top:16px;">Save changes</button>
        </form>
      </div>
    `;

    document.getElementById("company-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const alertBox = document.getElementById("company-alert");
      try {
        await Api.patch("/api/employers/me", {
          company_name: document.getElementById("company_name").value.trim(),
          industry: document.getElementById("industry").value.trim() || null,
          company_size: document.getElementById("company_size").value.trim() || null,
          website_url: document.getElementById("website_url").value.trim() || null,
          location: document.getElementById("location").value.trim() || null,
          company_description: document.getElementById("company_description").value.trim() || null,
        });
        alertBox.innerHTML = `<div class="alert alert-success">Company profile saved.</div>`;
      } catch (err) {
        alertBox.innerHTML = `<div class="alert alert-error">${escapeHtml(err.message)}</div>`;
      }
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

loadMyJobs();
