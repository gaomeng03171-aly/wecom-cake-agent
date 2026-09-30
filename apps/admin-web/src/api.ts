const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function getAdminKey(): string {
  return sessionStorage.getItem("adminApiKey") ?? "";
}

export function setAdminKey(value: string): void {
  if (value) {
    sessionStorage.setItem("adminApiKey", value);
  } else {
    sessionStorage.removeItem("adminApiKey");
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  const adminKey = getAdminKey();
  if (adminKey) {
    headers.set("X-Admin-Key", adminKey);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new ApiError(response.status, message || response.statusText);
  }

  return (await response.json()) as T;
}
