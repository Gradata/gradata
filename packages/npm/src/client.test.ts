import { describe, it, expect, vi } from "vitest";
import { GradataClient } from "./client.js";

function mockFetchOk(body: unknown): typeof globalThis.fetch {
  return vi.fn(async () =>
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  ) as unknown as typeof globalThis.fetch;
}

describe("GradataClient", () => {
  it("posts a correction payload with expected shape", async () => {
    const fetchSpy = vi.fn(async () =>
      new Response(JSON.stringify({ ok: true, correction_id: "c1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = new GradataClient({
      endpoint: "http://localhost:8765",
      fetch: fetchSpy as unknown as typeof globalThis.fetch,
    });
    const resp = await client.correct({
      draft: "We are pleased to inform you.",
      final: "Hey, check this out.",
      outputType: "email",
      selfScore: 7,
    });
    expect(resp.ok).toBe(true);
    expect(resp.correction_id).toBe("c1");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0]!;
    expect(url).toBe("http://localhost:8765/correct");
    expect((init as RequestInit).method).toBe("POST");
    const payload = JSON.parse((init as RequestInit).body as string);
    expect(payload.draft).toBe("We are pleased to inform you.");
    expect(payload.final).toBe("Hey, check this out.");
    expect(payload.output_type).toBe("email");
    expect(payload.self_score).toBe(7);
  });

  it("health() returns { ok: false } on network failure", async () => {
    const fetchSpy = vi.fn(async () => {
      throw new Error("ECONNREFUSED");
    });
    const client = new GradataClient({
      fetch: fetchSpy as unknown as typeof globalThis.fetch,
    });
    const h = await client.health();
    expect(h.ok).toBe(false);
  });

  it("rejects when daemon returns non-2xx", async () => {
    const fetchSpy = vi.fn(async () =>
      new Response(JSON.stringify({ error: "bad input" }), { status: 400 }),
    );
    const client = new GradataClient({
      fetch: fetchSpy as unknown as typeof globalThis.fetch,
    });
    await expect(
      client.correct({ draft: "x", final: "y" }),
    ).rejects.toThrow(/bad input/);
  });

  it("strips trailing slashes from endpoint", async () => {
    const fetchSpy = mockFetchOk({ ok: true });
    const client = new GradataClient({
      endpoint: "http://localhost:8765///",
      fetch: fetchSpy,
    });
    await client.health();
    const [url] = (fetchSpy as ReturnType<typeof vi.fn>).mock.calls[0]!;
    expect(url).toBe("http://localhost:8765/health");
  });
});
