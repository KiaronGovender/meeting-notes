"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  createMeeting,
  deleteMeeting,
  fmt,
  listMeetings,
  type Meeting,
} from "@/lib/api";

export default function Home() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = () =>
    listMeetings()
      .then(setMeetings)
      .catch((e) => setError(String(e.message)));
  useEffect(() => {
    load();
    const t = setInterval(load, 5000); // keep statuses fresh
    return () => clearInterval(t);
  }, []);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await createMeeting(url.trim(), title.trim() || "Untitled meeting");
      setUrl("");
      setTitle("");
      await load();
    } catch (err: any) {
      setError(err.message);
    }
    setBusy(false);
  }

  async function remove(e: React.MouseEvent, m: Meeting) {
    e.preventDefault(); // the row is a link, so don't navigate
    e.stopPropagation();
    if (
      !confirm(
        `Delete "${m.title}"? This removes its transcript, summary and highlights.`,
      )
    )
      return;
    try {
      await deleteMeeting(m.id);
      setMeetings((p) => p.filter((x) => x.id !== m.id));
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <div className="wrap">
      <header className="top">
        <h1>Notetaker</h1>
        <span className="mute">{meetings.length} meetings</span>
      </header>

      <form className="card" onSubmit={send}>
        <h2>Send the notetaker to a meeting</h2>
        <div className="row">
          <input
            placeholder="Meet, Zoom or Teams link"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
          />
          <input
            placeholder="Title (optional)"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <button disabled={busy || !url.trim()}>
            {busy ? "Sending…" : "Send bot"}
          </button>
        </div>
        {error && <div className="err">{error}</div>}
      </form>

      <div className="list">
        {meetings.length === 0 && (
          <div className="card mute">No meetings yet. Paste a link above.</div>
        )}
        {meetings.map((m) => (
          <Link key={m.id} href={`/meetings/${m.id}`} className="card item">
            <div>
              <div>{m.title}</div>
              <div className="mute">
                {new Date(m.created_at).toLocaleString()}
                {m.duration_ms ? ` · ${fmt(m.duration_ms)}` : ""}
              </div>
            </div>
            <div
              className="row"
              style={{ alignItems: "center", flexWrap: "nowrap" }}
            >
              <span className={`badge ${m.status}`}>{m.status}</span>
              <button
                className="x"
                title="Delete meeting"
                onClick={(e) => remove(e, m)}
              >
                ✕
              </button>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
