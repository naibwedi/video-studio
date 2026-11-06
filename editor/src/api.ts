declare global { interface Window { STUDIO_TOKEN: string } }

export async function api<T = any>(path: string, body?: unknown): Promise<T> {
  const init: RequestInit = body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json", "X-Studio-Token": window.STUDIO_TOKEN }, body: JSON.stringify(body),
  };
  const r = await fetch(path, init);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((j as any).error || r.statusText);
  return j as T;
}

export const thumbUrl = (id: string) => `/api/thumb/${id}`;
export const stripUrl = (id: string) => `/api/strip/${id}`;
export const clipUrl = (id: string) => `/api/clip/${id}`;
export const audioUrl = (name: string) => `/audio/${name}`;
export const isLibraryClip = (id: string) => /^(pb)?\d+$/.test(id);
