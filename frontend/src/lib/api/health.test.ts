import { afterEach, describe, expect, it, vi } from "vitest";

import { getHealth } from "./health";

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })));
}

describe("getHealth", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns the report when every dependency is healthy", async () => {
    mockFetch(200, { status: "ok", checks: { postgres: "ok" } });

    await expect(getHealth()).resolves.toEqual({ status: "ok", checks: { postgres: "ok" } });
  });

  it("treats a 503 with a valid report as a degraded system, not an error", async () => {
    mockFetch(503, { status: "degraded", checks: { chroma: "down" } });

    await expect(getHealth()).resolves.toEqual({
      status: "degraded",
      checks: { chroma: "down" },
    });
  });

  it("throws on any other failure", async () => {
    mockFetch(500, { detail: "boom" });

    await expect(getHealth()).rejects.toThrow("status 500");
  });
});
