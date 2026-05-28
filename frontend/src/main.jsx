import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API_CANDIDATES = [
  "",
  import.meta.env.VITE_API_URL,
  localStorage.getItem("deploy_lab_api_url"),
  "http://127.0.0.1:8020",
  "http://localhost:8020",
  "http://127.0.0.1:8001",
  "http://localhost:8001",
].filter(Boolean);

function api(apiBase, path, options) {
  return fetch(`${apiBase}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  }).then(async (response) => {
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${response.status}`);
    }
    return response.json();
  });
}

async function resolveApiBase() {
  for (const candidate of API_CANDIDATES) {
    const apiBase = candidate.replace(/\/$/, "");
    try {
      const response = await fetch(`${apiBase}/health`, { method: "GET" });
      if (response.ok) {
        if (apiBase) {
          localStorage.setItem("deploy_lab_api_url", apiBase);
        }
        return apiBase;
      }
    } catch {
      // Try the next local backend candidate.
    }
  }
  throw new Error(
    "Could not reach backend. Start it on port 8020 or set VITE_API_URL.",
  );
}

function App() {
  const [apiBase, setApiBase] = useState("");
  const [health, setHealth] = useState(null);
  const [stats, setStats] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");

  const orderedTasks = useMemo(
    () => [...tasks].sort((a, b) => b.id - a.id),
    [tasks],
  );

  async function refresh() {
    setError("");
    try {
      const base = apiBase || (await resolveApiBase());
      setApiBase(base);
      const [nextHealth, nextStats, nextTasks] = await Promise.all([
        api(base, "/health"),
        api(base, "/api/stats"),
        api(base, "/api/tasks"),
      ]);
      setHealth(nextHealth);
      setStats(nextStats);
      setTasks(nextTasks);
    } catch (err) {
      setError(err.message);
    }
  }

  async function addTask(event) {
    event.preventDefault();
    if (!title.trim()) return;
    const base = apiBase || (await resolveApiBase());
    setApiBase(base);
    await api(base, "/api/tasks", {
      method: "POST",
      body: JSON.stringify({ title: title.trim(), notes: "Created from UI" }),
    });
    setTitle("");
    await refresh();
  }

  async function advance(task) {
    const next = task.status === "queued" ? "running" : "done";
    const base = apiBase || (await resolveApiBase());
    setApiBase(base);
    await api(base, `/api/tasks/${task.id}/status/${next}`, { method: "PATCH" });
    await refresh();
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <main className="page">
      <section className="topbar">
        <div>
          <p className="eyebrow">Deploy Lab</p>
          <h1>Full-stack deployment smoke test</h1>
          <p className="apiBase">{apiBase || "Finding backend..."}</p>
        </div>
        <button onClick={refresh}>Refresh</button>
      </section>

      {error ? <div className="error">{error}</div> : null}

      <section className="metrics">
        <Metric label="API" value={health?.ok ? "Online" : "Checking"} />
        <Metric label="Database" value={health?.database || "-"} />
        <Metric label="Total tasks" value={stats?.total ?? "-"} />
        <Metric label="Done" value={stats?.done ?? "-"} />
      </section>

      <section className="workspace">
        <form onSubmit={addTask} className="composer">
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Add a deployment checklist item"
          />
          <button type="submit">Add</button>
        </form>

        <div className="taskList">
          {orderedTasks.map((task) => (
            <article className="task" key={task.id}>
              <div>
                <span className={`status ${task.status}`}>{task.status}</span>
                <h2>{task.title}</h2>
                <p>{task.notes}</p>
              </div>
              {task.status !== "done" ? (
                <button onClick={() => advance(task)}>Advance</button>
              ) : null}
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

function Metric({ label, value }) {
  return (
    <article className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

createRoot(document.getElementById("root")).render(<App />);
