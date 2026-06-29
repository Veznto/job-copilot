


function getApiBase() {
  // If running locally via file explorer or a dev port that isn't 8000
  if (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost" || window.location.protocol === "file:") {
    return "http://127.0.0.1:8000";
  }
  // When live on Render, point directly to the site's own origin URL
  return window.location.origin;
}
const API = getApiBase();
const PIPELINE_KEY = "copilot_pipeline";
let token = localStorage.getItem("copilot_token");
let userEmail = localStorage.getItem("copilot_email");
let currentRoleId = null;
let allRoles = [];
let pipelineRunning = false;

// ─── INIT ────────────────────────────────────────────────────────────────────

window.onload = async () => {
  if (token) {
    showApp();
    await resumePipelineIfNeeded();
  } else {
    showAuth();
  }
};

// ─── AUTH ────────────────────────────────────────────────────────────────────

function showAuth() {
  document.getElementById("auth-screen").classList.remove("hidden");
  document.getElementById("app-screen").classList.add("hidden");
}

function showApp() {
  document.getElementById("auth-screen").classList.add("hidden");
  document.getElementById("app-screen").classList.remove("hidden");
  document.getElementById("user-email-display").textContent = userEmail || "";
  loadRoles();
  if (!getPipelineState() && !pipelineRunning) {
    showWelcome();
  }
}

function switchTab(tab) {
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".auth-form").forEach(f => f.classList.add("hidden"));
  
  if (tab === "login") {
    document.querySelectorAll(".tab-btn")[0].classList.add("active");
    document.getElementById("login-form").classList.remove("hidden");
  } else {
    document.querySelectorAll(".tab-btn")[1].classList.add("active");
    document.getElementById("register-form").classList.remove("hidden");
  }
}

async function login() {
  const email = document.getElementById("login-email").value;
  const password = document.getElementById("login-password").value;
  
  if (!email || !password) {
    document.getElementById("login-error").textContent = "Please fill in all fields.";
    return;
  }

  // FastAPI's login endpoint requires form data
  const formData = new URLSearchParams();
  formData.append("username", email);
  formData.append("password", password);

  try {
    const res = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formData
    });
    
    const data = await res.json();
    if (!res.ok) {
      document.getElementById("login-error").textContent = data.detail || "Login failed.";
      return;
    }
    
    token = data.access_token;
    userEmail = email;
    localStorage.setItem("copilot_token", token);
    localStorage.setItem("copilot_email", email);
    showApp();
  } catch (err) {
    document.getElementById("login-error").textContent = "Connection error. Is the backend running?";
  }
}

async function register() {
  const email = document.getElementById("reg-email").value;
  const password = document.getElementById("reg-password").value;
  
  if (!email || !password) {
    document.getElementById("reg-error").textContent = "Please fill in all fields.";
    return;
  }
  if (password.length < 6) {
    document.getElementById("reg-error").textContent = "Password must be at least 6 characters.";
    return;
  }

  try {
    const res = await fetch(`${API}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    
    const data = await res.json();
    if (!res.ok) {
      document.getElementById("reg-error").textContent = data.detail || "Registration failed.";
      return;
    }
    
    token = data.access_token;
    userEmail = email;
    localStorage.setItem("copilot_token", token);
    localStorage.setItem("copilot_email", email);
    showApp();
  } catch (err) {
    document.getElementById("reg-error").textContent = "Connection error. Is the backend running?";
  }
}

function signOut() {
  token = null;
  userEmail = null;
  localStorage.removeItem("copilot_token");
  localStorage.removeItem("copilot_email");
  showAuth();
}

// ─── VIEWS ───────────────────────────────────────────────────────────────────

function showView(viewId) {
  document.querySelectorAll(".view").forEach(v => {
    v.classList.add("hidden");
    v.style.display = "";
  });
  const view = document.getElementById(viewId);
  view.classList.remove("hidden");
  if (viewId === "loading-view") {
    view.style.display = "flex";
  }
}

function showWelcome() { showView("welcome-view"); }
function showNewApplication() {
  document.getElementById("job-title").value = "";
  document.getElementById("company").value = "";
  document.getElementById("jd-text").value = "";
  document.getElementById("file-label").textContent = "Click to upload your resume PDF";
  document.getElementById("form-error").textContent = "";
  showView("new-app-view");
}

// ─── ROLES LIST ──────────────────────────────────────────────────────────────

async function loadRoles() {
  try {
    const res = await fetch(`${API}/applications`, {
      headers: { "Authorization": `Bearer ${token}` }
    });
    
    if (res.status === 401) { signOut(); return; }
    
    allRoles = await res.json();
    renderRolesList();
  } catch (err) {
    console.error("Failed to load roles:", err);
  }
}

function renderRolesList() {
  const list = document.getElementById("roles-list");
  
  if (allRoles.length === 0) {
    list.innerHTML = '<div class="empty-state-sidebar">No applications yet.<br>Create your first one!</div>';
    return;
  }
  
  list.innerHTML = allRoles.map(role => `
    <div class="role-item ${currentRoleId === role.id ? 'active' : ''}" 
         onclick="openRole(${role.id})">
      <div class="role-item-title">${role.job_title}</div>
      <div class="role-item-company">${role.company}</div>
      <span class="role-item-status status-${role.status}">${capitalize(role.status)}</span>
    </div>
  `).join("");
}

function capitalize(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

// ─── FILE UPLOAD ─────────────────────────────────────────────────────────────

function handleFileSelect(input) {
  if (input.files[0]) {
    document.getElementById("file-label").textContent = `✓ ${input.files[0].name}`;
    document.getElementById("drop-zone").style.borderColor = "var(--success)";
  }
}

// ─── PIPELINE STATE (survives page reloads) ──────────────────────────────────

function savePipelineState(roleId) {
  sessionStorage.setItem(PIPELINE_KEY, JSON.stringify({ role_id: roleId, started_at: Date.now() }));
}

function getPipelineState() {
  try {
    const raw = sessionStorage.getItem(PIPELINE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function clearPipelineState() {
  sessionStorage.removeItem(PIPELINE_KEY);
}

async function resumePipelineIfNeeded() {
  const pending = getPipelineState();
  if (!pending?.role_id) return;

  pipelineRunning = true;
  showView("loading-view");
  resetPipelineProgress();
  setLoadingStatus("Resuming AI pipeline...");

  try {
    await waitForPipelineComplete(pending.role_id);
  } catch (err) {
    clearPipelineState();
    showView("new-app-view");
    document.getElementById("form-error").textContent = err.message || "Pipeline failed.";
  } finally {
    pipelineRunning = false;
  }
}

async function waitForPipelineComplete(roleId) {
  await pollPipelineUntilComplete(roleId);
  clearPipelineState();
  await loadRoles();
  await openRole(roleId);
}

// ─── RUN PIPELINE ────────────────────────────────────────────────────────────

const AGENT_LABELS = {
  prepare: "Reading your resume",
  fit_analysis: "Fit Analysis Agent",
  resume_rewrite: "Resume Rewrite Agent",
  cover_letter: "Cover Letter Agent",
  interview_qa: "Interview Prep Agent",
};

async function runPipeline() {
  const jobTitle = document.getElementById("job-title").value.trim();
  const company = document.getElementById("company").value.trim();
  const jdText = document.getElementById("jd-text").value.trim();
  const fileInput = document.getElementById("resume-file");
  const runBtn = document.getElementById("run-btn");

  if (!jobTitle || !company || !jdText) {
    document.getElementById("form-error").textContent = "Please fill in all fields.";
    return;
  }
  if (!fileInput.files[0]) {
    document.getElementById("form-error").textContent = "Please upload your resume PDF.";
    return;
  }

  document.getElementById("form-error").textContent = "";
  runBtn.disabled = true;
  runBtn.textContent = "Running...";
  resetPipelineProgress();
  showView("loading-view");
  pipelineRunning = true;

  const formData = new FormData();
  formData.append("job_title", jobTitle);
  formData.append("company", company);
  formData.append("jd_text", jdText);
  formData.append("resume", fileInput.files[0]);

  try {
    const res = await fetch(`${API}/applications/start`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${token}` },
      body: formData,
    });

    let data;
    try {
      data = await res.json();
    } catch {
      throw new Error(
        res.status === 404
          ? "Backend not updated. Restart the server: uvicorn main:app --reload"
          : "Unexpected server response."
      );
    }

    if (!res.ok) {
      throw new Error(data.detail || "Pipeline failed to start.");
    }

    if (!data.role_id) {
      throw new Error("Server did not return a role ID.");
    }

    savePipelineState(data.role_id);
    await loadRoles();
    await waitForPipelineComplete(data.role_id);
  } catch (err) {
    const pending = getPipelineState();
    if (pending?.role_id) {
      showView("loading-view");
      setLoadingStatus("Reconnecting to running pipeline...");
      try {
        await waitForPipelineComplete(pending.role_id);
        return;
      } catch {
        clearPipelineState();
      }
    }
    showView("new-app-view");
    document.getElementById("form-error").textContent = err.message || "Connection error.";
  } finally {
    pipelineRunning = false;
    runBtn.disabled = false;
    runBtn.textContent = "Run AI Pipeline →";
  }
}

async function pollPipelineUntilComplete(roleId) {
  const POLL_MS = 1500;

  while (true) {
    showView("loading-view");

    const res = await fetch(`${API}/applications/${roleId}/pipeline-status`, {
      headers: { "Authorization": `Bearer ${token}` },
    });

    if (res.status === 401) {
      signOut();
      throw new Error("Session expired. Please sign in again.");
    }

    let status;
    try {
      status = await res.json();
    } catch {
      throw new Error("Lost connection to server. Is the backend still running?");
    }

    if (!res.ok) {
      throw new Error(status.detail || "Could not check pipeline status.");
    }

    applyPipelineStatus(status);

    if (status.status === "complete") {
      markAllStepsDone();
      setLoadingStatus("All agents finished! Loading your results...");
      return;
    }

    if (status.status === "error") {
      throw new Error(status.message || "AI pipeline failed.");
    }

    await sleep(POLL_MS);
  }
}

function applyPipelineStatus(status) {
  if (status.message) {
    setLoadingStatus(status.message);
  }

  if (status.step >= 1 && status.step <= 4) {
    updatePipelineProgress({
      step: status.step,
      agent: status.agent,
      status: status.agent_status || "started",
      message: status.message,
    });
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function resetPipelineProgress() {
  for (let i = 1; i <= 4; i++) {
    const step = document.getElementById(`step-${i}`);
    if (step) step.classList.remove("active", "done");
  }
  document.querySelectorAll(".pipeline-connector").forEach(c => {
    c.classList.remove("active", "done");
  });
  setLoadingStatus("Preparing your application...");
}

function updatePipelineProgress(event) {
  const { step, agent, status, message } = event;

  if (message) {
    setLoadingStatus(message);
  } else if (status === "started") {
    setLoadingStatus(`Running ${AGENT_LABELS[agent] || agent}...`);
  } else if (status === "completed") {
    setLoadingStatus(`${AGENT_LABELS[agent] || agent} complete`);
  }

  if (step >= 1 && step <= 4) {
    const stepEl = document.getElementById(`step-${step}`);
    const connector = stepEl?.previousElementSibling;

    if (status === "started") {
      for (let i = 1; i < step; i++) {
        document.getElementById(`step-${i}`)?.classList.add("done");
        document.getElementById(`step-${i}`)?.classList.remove("active");
      }
      stepEl?.classList.add("active");
      stepEl?.classList.remove("done");
      if (connector?.classList.contains("pipeline-connector")) {
        connector.classList.add("active");
      }
    } else if (status === "completed") {
      for (let i = 1; i <= step; i++) {
        document.getElementById(`step-${i}`)?.classList.remove("active");
        document.getElementById(`step-${i}`)?.classList.add("done");
      }
      stepEl?.classList.remove("active");
      stepEl?.classList.add("done");
      if (connector?.classList.contains("pipeline-connector")) {
        connector.classList.remove("active");
        connector.classList.add("done");
      }
    }
  }
}

function markAllStepsDone() {
  for (let i = 1; i <= 4; i++) {
    const step = document.getElementById(`step-${i}`);
    step?.classList.remove("active");
    step?.classList.add("done");
  }
  document.querySelectorAll(".pipeline-connector").forEach(c => {
    c.classList.remove("active");
    c.classList.add("done");
  });
}

function setLoadingStatus(text) {
  const el = document.getElementById("loading-status");
  if (el) el.textContent = text;
}

// ─── OPEN ROLE ───────────────────────────────────────────────────────────────

function openRole(roleId) {
  return openRoleAsync(roleId);
}

async function openRoleAsync(roleId) {
  currentRoleId = roleId;

  let role = allRoles.find(r => r.id === roleId);
  if (!role) {
    try {
      const res = await fetch(`${API}/applications/${roleId}`, {
        headers: { "Authorization": `Bearer ${token}` },
      });
      if (res.ok) {
        role = await res.json();
        const idx = allRoles.findIndex(r => r.id === roleId);
        if (idx >= 0) allRoles[idx] = role;
        else allRoles.unshift(role);
      }
    } catch (err) {
      console.error("Failed to load application:", err);
    }
  }

  renderRolesList();

  if (!role) return;
  
  const draft = role.drafts?.[0];
  
  document.getElementById("results-title").textContent = `${role.job_title} at ${role.company}`;
  document.getElementById("status-select").value = role.status;
  
  // Populate content
  document.getElementById("fit-content").textContent = draft?.fit_analysis || "No data yet.";
  document.getElementById("resume-content").textContent = draft?.resume_rewrite || "No data yet.";
  document.getElementById("original-content").textContent = role.original_resume_text || "Original resume not saved.";
  document.getElementById("cover-content").textContent = draft?.cover_letter || "No data yet.";
  document.getElementById("interview-content").textContent = draft?.interview_qa || "No data yet.";
  
  showResultTab("fit");
  showView("results-view");
}

// ─── RESULT TABS ─────────────────────────────────────────────────────────────

function showResultTab(tab) {
  document.querySelectorAll(".result-tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".result-panel").forEach(p => p.classList.add("hidden"));
  
  const tabMap = { fit: 0, resume: 1, cover: 2, interview: 3 };
  document.querySelectorAll(".result-tab")[tabMap[tab]].classList.add("active");
  document.getElementById(`${tab}-panel`).classList.remove("hidden");
}

function showDiff(which) {
  document.querySelectorAll(".diff-btn").forEach(b => b.classList.remove("active"));
  event.target.classList.add("active");
  
  if (which === "rewritten") {
    document.getElementById("resume-content").classList.remove("hidden");
    document.getElementById("original-content").classList.add("hidden");
  } else {
    document.getElementById("resume-content").classList.add("hidden");
    document.getElementById("original-content").classList.remove("hidden");
  }
}

// ─── UPDATE STATUS ───────────────────────────────────────────────────────────

async function updateStatus() {
  const newStatus = document.getElementById("status-select").value;
  
  await fetch(`${API}/applications/${currentRoleId}`, {
    method: "PATCH",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ status: newStatus })
  });
  
  await loadRoles();
}

// ─── DELETE ──────────────────────────────────────────────────────────────────

async function deleteApplication() {
  if (!confirm("Delete this application? This cannot be undone.")) return;
  
  await fetch(`${API}/applications/${currentRoleId}`, {
    method: "DELETE",
    headers: { "Authorization": `Bearer ${token}` }
  });
  
  currentRoleId = null;
  await loadRoles();
  showWelcome();
}

// ─── COPY ────────────────────────────────────────────────────────────────────

function copyContent(elementId) {
  const text = document.getElementById(elementId).textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = event.target;
    btn.textContent = "Copied!";
    btn.style.color = "var(--success)";
    setTimeout(() => { btn.textContent = "Copy"; btn.style.color = ""; }, 2000);
  });
}