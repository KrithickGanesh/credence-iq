import type {
  AdverseActionResponse,
  ApplicantDetailResponse,
  ApplicationsResponse,
  HealthResponse,
  OverviewResponse,
  SimulationRequest,
  SimulationResponse,
  UdfScoringResponse,
} from "./types";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(message: string, status = 0, detail = "") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60_000);
  try {
    const response = await fetch(`${API_URL}${path}`, {
      ...init,
      cache: "no-store",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
    if (!response.ok) {
      let detail = `Request failed with status ${response.status}`;
      try {
        const body = (await response.json()) as { detail?: string; error?: string };
        detail = body.detail || body.error || detail;
      } catch {
        // Keep the HTTP status message when the body is not JSON.
      }
      throw new ApiError(detail, response.status, detail);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("The API request timed out. Exasol may still be starting.", 0);
    }
    throw new ApiError(
      "Unable to reach the CredenceIQ API. Confirm the backend is running on port 8000.",
      0,
    );
  } finally {
    clearTimeout(timeout);
  }
}

function query(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const value = search.toString();
  return value ? `?${value}` : "";
}

export const api = {
  baseUrl: API_URL,

  health: () => request<HealthResponse>("/api/health"),

  overview: () => request<OverviewResponse>("/api/overview"),

  udfScoring: () => request<UdfScoringResponse>("/api/scoring/udf"),

  applications: (params: {
    page?: number;
    page_size?: number;
    search?: string;
    decision?: string;
    eligibility_decision?: string;
    discrepancy_only?: boolean;
    sort?: string;
    direction?: "asc" | "desc";
  }) => request<ApplicationsResponse>(`/api/applications${query(params)}`),

  reconciliation: (customerId: number) =>
    request<ApplicantDetailResponse>(`/api/applicant/${customerId}/reconciliation`),

  simulate: (customerId: number, body: SimulationRequest) =>
    request<SimulationResponse>(`/api/applicant/${customerId}/simulate`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  adverseAction: (customerId: number, body: { tone?: string; include_state_disclosure?: boolean } = {}) =>
    request<AdverseActionResponse>(`/api/applicant/${customerId}/adverse-action`, {
      method: "POST",
      body: JSON.stringify({
        tone: body.tone ?? "formal",
        include_state_disclosure: body.include_state_disclosure ?? true,
      }),
    }),
};
