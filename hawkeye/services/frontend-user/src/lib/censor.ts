// The User Console is the AUTHENTICATED view. The signed-in user is authorized
// to see their own GCP project's real resource names / ids / emails, so we do
// NOT censor anything here. These are identity (pass-through) functions.
//
// (The public demo console in services/frontend-demo uses the real censoring
// implementation to avoid leaking data on a shared, unauthenticated URL.)

export function censorId(id: string): string {
  return id;
}

export function censorName(name?: string): string {
  return name ?? "—";
}

export function censorEmail(email?: string | null): string {
  return email ?? "—";
}

export function censorText(text?: string): string {
  return text ?? "";
}
