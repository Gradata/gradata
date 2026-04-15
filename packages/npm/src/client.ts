/**
 * @gradata/cli — minimal JS correction client.
 *
 * Posts correction events to a local Gradata daemon (default
 * http://127.0.0.1:8765). The daemon converts them into behavioural
 * rules via the graduation pipeline. Pure fetch, no dependencies.
 *
 * Usage:
 *   import { GradataClient } from "@gradata/cli";
 *   const client = new GradataClient({ endpoint: "http://127.0.0.1:8765" });
 *   await client.correct({
 *     draft: "We are pleased to inform you ...",
 *     final: "Hey, check this out.",
 *     outputType: "email",
 *   });
 */

export interface GradataClientOptions {
  /** Daemon base URL. Defaults to http://127.0.0.1:8765. */
  endpoint?: string;
  /** Request timeout in ms. Defaults to 5000. */
  timeoutMs?: number;
  /** Optional fetch implementation (tests inject a mock). */
  fetch?: typeof globalThis.fetch;
}

export interface CorrectionRequest {
  draft: string;
  final: string;
  outputType?: string;
  taskType?: string;
  selfScore?: number;
  metadata?: Record<string, unknown>;
}

export interface CorrectionResponse {
  ok: boolean;
  /** Daemon echoes a correction id when accepted. */
  correction_id?: string;
  /** Daemon echoes severity (trivial/minor/moderate/major/rewrite). */
  severity?: string;
  /** Daemon message on failure. */
  error?: string;
}

export interface HealthResponse {
  ok: boolean;
  sdk_version?: string;
  sessions?: number;
}

const DEFAULT_ENDPOINT = "http://127.0.0.1:8765";
const DEFAULT_TIMEOUT_MS = 5000;

export class GradataClient {
  private readonly endpoint: string;
  private readonly timeoutMs: number;
  private readonly fetchImpl: typeof globalThis.fetch;

  constructor(opts: GradataClientOptions = {}) {
    this.endpoint = (opts.endpoint ?? DEFAULT_ENDPOINT).replace(/\/+$/, "");
    this.timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    const chosen = opts.fetch ?? globalThis.fetch;
    if (typeof chosen !== "function") {
      throw new Error(
        "No fetch implementation available. Node 18+ or provide opts.fetch.",
      );
    }
    this.fetchImpl = chosen;
  }

  /** Emit a correction event to the daemon. */
  async correct(req: CorrectionRequest): Promise<CorrectionResponse> {
    const body = {
      draft: req.draft,
      final: req.final,
      output_type: req.outputType,
      task_type: req.taskType,
      self_score: req.selfScore,
      metadata: req.metadata,
    };
    return this.post<CorrectionResponse>("/correct", body);
  }

  /** Ping the daemon. Returns `{ok:false}` with error if unreachable. */
  async health(): Promise<HealthResponse> {
    try {
      return await this.get<HealthResponse>("/health");
    } catch {
      return { ok: false };
    }
  }

  private async post<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>("POST", path, body);
  }

  private async get<T>(path: string): Promise<T> {
    return this.request<T>("GET", path, undefined);
  }

  private async request<T>(
    method: "GET" | "POST",
    path: string,
    body: unknown,
  ): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const init: RequestInit = {
        method,
        signal: controller.signal,
      };
      if (method === "POST") {
        init.headers = { "Content-Type": "application/json" };
        init.body = JSON.stringify(body);
      }
      const res = await this.fetchImpl(`${this.endpoint}${path}`, init);
      const text = await res.text();
      let parsed: unknown = {};
      if (text) {
        try {
          parsed = JSON.parse(text);
        } catch {
          throw new Error(
            `Gradata daemon returned non-JSON (${res.status}): ${text.slice(0, 200)}`,
          );
        }
      }
      if (!res.ok) {
        const msg =
          (parsed as { error?: string })?.error ??
          `HTTP ${res.status} from ${path}`;
        throw new Error(msg);
      }
      return parsed as T;
    } finally {
      clearTimeout(timer);
    }
  }
}

export default GradataClient;
