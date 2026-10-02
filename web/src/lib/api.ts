export const API = process.env.NEXT_PRIVATE_API_URL ?? "http://127.0.0.1:8000";

export type Segment = {
  id: number;
  speaker: string;
  start_ms: number;
  end_ms: number;
  text: string;
};
export type Meeting = {
  id: number;
  title: string;
  status: string;
  meeting_url: string | null;
  duration_ms: number | null;
  created_at: string;
  segments?: Segment[];
  highlights?: Highlight[];
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json();
}

export const listMeetings = () => req<Meeting[]>("/meetings");
export const getMeeting = (id: number | string) =>
  req<Meeting>(`/meetings/${id}`);
export const getMedia = (id: number | string) =>
  req<{ video?: string; audio?: string }>(`/meetings/${id}/media`);
export const createMeeting = (meeting_url: string, title: string) =>
  req<Meeting>("/meetings", {
    method: "POST",
    body: JSON.stringify({ meeting_url, title }),
  });

export const fmt = (ms: number) => {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600),
    m = Math.floor((s % 3600) / 60),
    sec = s % 60;
  const p = (n: number) => String(n).padStart(2, "0");
  return h ? `${h}:${p(m)}:${p(sec)}` : `${m}:${p(sec)}`;
};

export type ActionItem = {
  id: number;
  text: string;
  owner: string | null;
  at_ms: number | null;
  done: boolean;
};
export type SummaryResult = {
  template: string;
  content: { overview: string; sections: { title: string; items: string[] }[] };
  action_items: ActionItem[];
};
export const TEMPLATES = [
  { id: "general", label: "General" },
  { id: "sales", label: "Sales call" },
  { id: "one_on_one", label: "1:1" },
  { id: "standup", label: "Standup" },
];
export const getSummary = (
  id: number | string,
  template: string,
  force = false,
) =>
  req<SummaryResult>(`/meetings/${id}/summary`, {
    method: "POST",
    body: JSON.stringify({ template, force }),
  });

export type Highlight = {
  id: number;
  start_ms: number;
  end_ms: number | null;
  note: string | null;
};

export const addHighlight = (
  id: number | string,
  start_ms: number,
  end_ms: number | null,
) =>
  req<Highlight>(`/meetings/${id}/highlights`, {
    method: "POST",
    body: JSON.stringify({ start_ms, end_ms }),
  });

export const updateHighlight = (hid: number, note: string) =>
  req<Highlight>(`/highlights/${hid}`, {
    method: "PATCH",
    body: JSON.stringify({ note }),
  });

export const deleteHighlight = (hid: number) =>
  req<{ ok: boolean }>(`/highlights/${hid}`, { method: "DELETE" });

export const deleteMeeting = (id: number | string) =>
  req<{ ok: boolean }>(`/meetings/${id}`, { method: "DELETE" });
