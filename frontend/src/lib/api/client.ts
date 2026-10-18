const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: unknown,
  ) {
    super(`API request failed with status ${status}`);
    this.name = "ApiError";
  }
}

/**
 * Single entry point to the backend. Every feature talks to the API through here,
 * so base URL, headers and error handling change in one place.
 */
export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  });
  const body: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(response.status, body);
  }
  return body as T;
}
