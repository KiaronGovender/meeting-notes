"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  addHighlight,
  deleteHighlight,
  deleteMeeting,
  fmt,
  getMedia,
  getMeeting,
  getSummary,
  TEMPLATES,
  updateHighlight,
  type Highlight,
  type Meeting,
  type SummaryResult,
} from "@/lib/api";

const hue = (s: string) =>
  [...s].reduce((a, c) => a + c.charCodeAt(0) * 17, 0) % 360;

export default function MeetingPage() {
  const { id } = useParams<{ id: string }>();
  const [m, setM] = useState<Meeting | null>(null);
  const [media, setMedia] = useState<{ video?: string; audio?: string }>();
  const [now, setNow] = useState(0);
  const [dur, setDur] = useState(0);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const player = useRef<HTMLVideoElement>(null);
  const audioEl = useRef<HTMLAudioElement>(null);
  const [tpl, setTpl] = useState("general");
  const [sums, setSums] = useState<Record<string, SummaryResult>>({});
  const [sumErr, setSumErr] = useState("");
  const [loadingSum, setLoadingSum] = useState(false);
  const inflight = useRef(new Set<string>());
  const [hl, setHl] = useState<Highlight[]>([]);
  const items = Object.values(sums)[0]?.action_items ?? [];
  const router = useRouter();

  const removeMeeting = async () => {
    if (
      !m ||
      !confirm(
        `Delete "${m.title}"? This removes its transcript, summary and highlights.`,
      )
    )
      return;
    try {
      await deleteMeeting(id);
      router.push("/");
    } catch (e: any) {
      setError(e.message);
    }
  };

  const loadSummary = (t: string, force = false) => {
    const key = `${id}:${t}`;
    if (inflight.current.has(key)) return;
    inflight.current.add(key);
    setLoadingSum(true);
    setSumErr("");
    getSummary(id, t, force)
      .then((r) => setSums((p) => (force ? { [t]: r } : { ...p, [t]: r })))
      .catch((e) => setSumErr(e.message))
      .finally(() => {
        inflight.current.delete(key);
        setLoadingSum(false);
      });
  };
  useEffect(() => {
    if (m?.status === "done" && (m.segments?.length ?? 0) > 0 && !sums[tpl])
      loadSummary(tpl);
  }, [m?.status, m?.segments?.length, tpl]);

  // Poll while the bot is still working.
  useEffect(() => {
    let stop = false;
    const tick = async () => {
      try {
        const data = await getMeeting(id);
        if (stop) return;
        setM(data);
        if (data.status !== "done" && data.status !== "failed")
          setTimeout(tick, 4000);
      } catch (e: any) {
        setError(e.message);
      }
    };
    tick();
    return () => {
      stop = true;
    };
  }, [id]);

  useEffect(() => {
    setHl(m?.highlights ?? []);
  }, [m?.id, m?.status]);

  useEffect(() => {
    if (m?.status === "done" && !media)
      getMedia(id)
        .then(setMedia)
        .catch(() => {});
  }, [m?.status, id, media]);

  const segs = m?.segments ?? [];
  const shown = useMemo(
    () =>
      q
        ? segs.filter((s) =>
            (s.text + s.speaker).toLowerCase().includes(q.toLowerCase()),
          )
        : segs,
    [segs, q],
  );
  const active = segs.findLast((s) => s.start_ms <= now * 1000)?.id;

  useEffect(() => {
    document
      .getElementById(`seg-${active}`)
      ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [active]);

  const seek = (ms: number) => {
    if (!player.current) return;
    player.current.currentTime = ms / 1000;
    player.current.play();
  };

  const sync = (e: React.SyntheticEvent<HTMLVideoElement>, play?: boolean) => {
    const a = audioEl.current,
      v = e.currentTarget;
    if (!a) return;
    if (Math.abs(a.currentTime - v.currentTime) > 0.3)
      a.currentTime = v.currentTime;
    if (play === true) a.play().catch(() => {});
    if (play === false) a.pause();
  };

  // Highlight = 5s before to 25s after the current moment.
  const addHere = async () => {
    const t = player.current?.currentTime ?? 0;
    const start = Math.max(0, Math.round((t - 5) * 1000));
    let end = Math.round((t + 25) * 1000);
    if (dur > 0) end = Math.min(end, Math.round(dur * 1000));
    if (end <= start) end = start + 1000;
    try {
      const h = await addHighlight(id, start, end);
      setHl((p) => [...p, h].sort((a, b) => a.start_ms - b.start_ms));
    } catch (e: any) {
      setError(e.message);
    }
  };
  const addRef = useRef(addHere);
  addRef.current = addHere;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (
        e.key.toLowerCase() === "h" &&
        !e.metaKey &&
        !e.ctrlKey &&
        tag !== "INPUT" &&
        tag !== "TEXTAREA"
      )
        addRef.current();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const saveNote = async (h: Highlight, note: string) => {
    if (note.trim() === (h.note ?? "")) return;
    const u = await updateHighlight(h.id, note).catch(() => null);
    if (u) setHl((p) => p.map((x) => (x.id === u.id ? u : x)));
  };
  const remove = async (h: Highlight) => {
    await deleteHighlight(h.id).catch(() => null);
    setHl((p) => p.filter((x) => x.id !== h.id));
  };
  const snippet = (ms: number) => segs.find((s) => s.end_ms >= ms)?.text ?? "";

  if (error)
    return (
      <div className="wrap">
        <Link href="/">← Meetings</Link>
        <div className="err">{error}</div>
      </div>
    );
  if (!m) return <div className="wrap mute">Loading…</div>;

  return (
    <div className="wrap">
      <header className="top">
        <div>
          <Link href="/" className="mute">
            ← Meetings
          </Link>
          <h1>{m.title}</h1>
        </div>
        <div
          className="row"
          style={{ alignItems: "center", flexWrap: "nowrap" }}
        >
          <span className={`badge ${m.status}`}>{m.status}</span>
          <button className="x" onClick={removeMeeting}>
            Delete
          </button>
        </div>
      </header>

      {m.status !== "done" && (
        <div className="card mute">
          {m.status === "failed"
            ? "The bot could not finish this meeting."
            : "Working on it — this page updates automatically."}
        </div>
      )}

      {(media?.video || media?.audio) && (
        <>
          <video
            ref={player}
            src={media.video || media.audio}
            muted={!!(media.video && media.audio)}
            controls
            onLoadedMetadata={(e) => setDur(e.currentTarget.duration)}
            onTimeUpdate={(e) => {
              setNow(e.currentTarget.currentTime);
              sync(e);
            }}
            onPlay={(e) => sync(e, true)}
            onPause={(e) => sync(e, false)}
            onSeeked={(e) => sync(e)}
          />
          {media.video && media.audio && (
            <audio ref={audioEl} src={media.audio} preload="auto" />
          )}
          {dur > 0 && (
            <div className="tl">
              {hl.map((h) => (
                <button
                  key={h.id}
                  className="mk"
                  title={h.note || fmt(h.start_ms)}
                  style={{
                    left: `${Math.min(100, (h.start_ms / (dur * 1000)) * 100)}%`,
                  }}
                  onClick={() => seek(h.start_ms)}
                />
              ))}
            </div>
          )}
          <button className="hlbtn" onClick={addHere}>
            ★ Highlight this moment <span className="mute">(H)</span>
          </button>
        </>
      )}

      {segs.length > 0 && (
        <div className="grid2">
          <div className="card sec scroll">
            <div className="tabs">
              {TEMPLATES.map((t) => (
                <button
                  key={t.id}
                  className={`tab ${t.id === tpl ? "on" : ""}`}
                  onClick={() => setTpl(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </div>
            {loadingSum && !sums[tpl] && (
              <div className="mute">
                Writing the summary… a long call can take a minute or two.
              </div>
            )}
            {sumErr && (
              <div className="err">
                {sumErr}{" "}
                <button className="link" onClick={() => loadSummary(tpl, true)}>
                  Retry
                </button>
              </div>
            )}
            {sums[tpl] && (
              <>
                <p style={{ marginTop: 0 }}>{sums[tpl].content.overview}</p>
                {sums[tpl].content.sections.map((sec) => (
                  <div key={sec.title}>
                    <h3>{sec.title}</h3>
                    <ul>
                      {sec.items.map((it, i) => (
                        <li key={i}>{it}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </>
            )}
          </div>

          <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
            <div className="card scroll sm">
              <h2>Action items</h2>
              {items.length === 0 && (
                <div className="mute">{sums[tpl] ? "None found." : "…"}</div>
              )}
              {items.map((a) => (
                <div
                  key={a.id}
                  className="ai"
                  onClick={() => a.at_ms != null && seek(a.at_ms)}
                >
                  <div className="tx">{a.text}</div>
                  <div className="mute">
                    {a.owner ?? "Unassigned"}
                    {a.at_ms != null ? ` · ${fmt(a.at_ms)}` : ""}
                  </div>
                </div>
              ))}
            </div>

            <div className="card scroll sm">
              <h2>Highlights</h2>
              {hl.length === 0 && (
                <div className="mute">
                  Press ★ or H while watching to save a moment.
                </div>
              )}
              {hl.map((h) => (
                <div key={h.id} className="hl">
                  <div className="head" onClick={() => seek(h.start_ms)}>
                    <b>
                      {fmt(h.start_ms)}
                      {h.end_ms ? `–${fmt(h.end_ms)}` : ""}
                    </b>
                    <button
                      className="x"
                      onClick={(e) => {
                        e.stopPropagation();
                        remove(h);
                      }}
                      title="Delete"
                    >
                      ✕
                    </button>
                  </div>
                  <div className="snip">{snippet(h.start_ms)}</div>
                  <input
                    placeholder="Add a note"
                    defaultValue={h.note ?? ""}
                    onBlur={(e) => saveNote(h, e.target.value)}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {segs.length > 0 && (
        <div className="card tr" style={{ marginTop: 16 }}>
          <div className="row" style={{ marginBottom: 8 }}>
            <input
              placeholder="Search this transcript"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          {shown.map((s) => (
            <div
              key={s.id}
              id={`seg-${s.id}`}
              className={`seg ${s.id === active ? "on" : ""}`}
              onClick={() => seek(s.start_ms)}
            >
              <span className="t">{fmt(s.start_ms)}</span>
              <div>
                <b style={{ color: `hsl(${hue(s.speaker)} 70% 70%)` }}>
                  {s.speaker}
                </b>
                {s.text}
              </div>
            </div>
          ))}
          {shown.length === 0 && <div className="mute">No matches.</div>}
        </div>
      )}
    </div>
  );
}
