export function formatBytes(bytes: number, digits = 1): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** i;
  return `${value >= 100 || i === 0 ? Math.round(value) : value.toFixed(digits)} ${units[i]}`;
}

export function formatDate(iso: string | null | undefined, withTime = true): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
}

export function shortHash(hash: string | null | undefined): string {
  return hash ? `${hash.slice(0, 8)}…${hash.slice(-6)}` : "—";
}

export function titleCase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function describeAction(action: string): string {
  const map: Record<string, string> = {
    "auth.login": "Signed in",
    "auth.login_failed": "Failed sign-in",
    "auth.register": "Account created",
    "file.upload": "Uploaded files",
    "file.download": "Downloaded a file",
    "file.delete": "Deleted files",
    "file.protect": "Protected a file",
    "file.unprotect": "Removed protection",
    "duplicates.rescan": "Started a re-scan",
  };
  return map[action] ?? action;
}
