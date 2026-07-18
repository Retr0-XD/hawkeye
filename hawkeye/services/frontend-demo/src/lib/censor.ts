// Data censoring for the public demo.
// The demo is unauthenticated and shared publicly, so we mask identifying
// parts of resource ids/names while preserving the *structure* and *shape* of
// the data (project, type, region, relationships) so the visualization and
// ML reasoning remain meaningful. Original data is untouched in the backend;
// censoring is a presentation-layer concern for this public view only.

// Deterministic hash so the same id always censors to the same token.
function hashToken(input: string): string {
  let h = 2166136261;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0).toString(36).padStart(6, "0").slice(0, 6);
}

// Censor a resource id like "gcp://run/dice-master-the-platform/aether".
// Keeps the scheme + type, masks the project and the resource name.
export function censorId(id: string): string {
  if (!id) return id;
  const parts = id.split("/");
  if (parts.length < 4) return id;
  const [scheme, type, project, ...rest] = parts;
  const maskedProject = `proj-${hashToken(project).slice(0, 4)}`;
  const maskedName = rest.map((seg) => `***${hashToken(seg).slice(0, 3)}`).join("/");
  return `${scheme}//${type}/${maskedProject}/${maskedName}`;
}

// Censor a human name (e.g. "aether" -> "a***r").
export function censorName(name?: string): string {
  if (!name) return "—";
  if (name.length <= 2) return name[0] + "*";
  return name[0] + "*".repeat(Math.min(name.length - 2, 6)) + name[name.length - 1];
}

// Censor an email (e.g. "jane@corp.com" -> "j***@c***.com").
export function censorEmail(email?: string | null): string {
  if (!email || !email.includes("@")) return "—";
  const [user, domain] = email.split("@");
  const d = domain.split(".");
  const maskedDomain = d.map((p) => (p.length <= 1 ? p : p[0] + "***")).join(".");
  return `${user[0]}***@${maskedDomain}`;
}

// Censor any free-form string by masking the middle.
export function censorText(text?: string): string {
  if (!text) return "";
  if (text.length <= 6) return text;
  return text.slice(0, 3) + "•••" + text.slice(-3);
}
