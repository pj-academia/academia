import { ApiError, apiGet } from "./client";

export type DependencyStatus = "ok" | "down";

export interface HealthReport {
  status: "ok" | "degraded";
  checks: Record<string, DependencyStatus>;
}

/** /health answers 503 with a valid report when a dependency is down; that is data, not an error. */
export async function getHealth(): Promise<HealthReport> {
  try {
    return await apiGet<HealthReport>("/health", { cache: "no-store" });
  } catch (error) {
    if (error instanceof ApiError && error.status === 503 && isHealthReport(error.body)) {
      return error.body;
    }
    throw error;
  }
}

function isHealthReport(value: unknown): value is HealthReport {
  return typeof value === "object" && value !== null && "status" in value && "checks" in value;
}
