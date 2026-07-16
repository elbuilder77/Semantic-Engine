import type {
  AnalyticsData,
  ApiKeyListResponse,
  CreateApiKeyRequest,
  CreateApiKeyResponse,
  DocumentListResponse,
  HealthResponse,
  SearchRequest,
  SearchResponse,
} from "@/lib/types";

const DEFAULT_API_URL =
  process.env.NEXT_PUBLIC_SES_API_URL ?? "http://localhost:8000";

function getConnection(): { baseUrl: string; apiKey: string } {
  const storedUrl =
    typeof window === "undefined"
      ? DEFAULT_API_URL
      : localStorage.getItem("ses_api_url") || DEFAULT_API_URL;
  const apiKey =
    typeof window === "undefined"
      ? ""
      : localStorage.getItem("ses_api_key") || "";

  return {
    baseUrl: storedUrl.trim().replace(/\/+$/, ""),
    apiKey: apiKey.trim(),
  };
}

function getHeaders(apiKey: string, hasJsonBody: boolean): Headers {
  const headers = new Headers({ Accept: "application/json" });
  if (apiKey) headers.set("X-API-Key", apiKey);
  if (hasJsonBody) headers.set("Content-Type", "application/json");
  return headers;
}

async function errorMessage(response: Response): Promise<string> {
  const fallback = `${response.status} ${response.statusText}`.trim();
  try {
    const body = (await response.json()) as { detail?: unknown; message?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (typeof body.message === "string") return body.message;
  } catch {
    // The response is not JSON; use the HTTP status below.
  }
  return fallback || "Gateway request failed";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { baseUrl, apiKey } = getConnection();
  const hasJsonBody = typeof init.body === "string";
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    cache: "no-store",
    headers: getHeaders(apiKey, hasJsonBody),
  });

  if (!response.ok) throw new Error(await errorMessage(response));
  return (await response.json()) as T;
}

function filenameFrom(response: Response): string {
  const disposition = response.headers.get("content-disposition") || "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const plain = disposition.match(/filename="?([^";]+)"?/i)?.[1];

  if (encoded) return decodeURIComponent(encoded);
  if (plain) return plain;
  return "ses-report.pdf";
}

export const api = {
  getHealth: () => request<HealthResponse>("/api/v1/health"),

  getAnalytics: () =>
    request<AnalyticsData>("/api/v1/admin/analytics"),

  search: (payload: SearchRequest) =>
    request<SearchResponse>("/api/v1/search", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listDocuments: (limit = 50) =>
    request<DocumentListResponse>(
      `/api/v1/documents?limit=${encodeURIComponent(limit)}`,
    ),

  ingestFile: async (file: File) => {
    const { baseUrl, apiKey } = getConnection();
    const body = new FormData();
    body.append("file", file);

    const response = await fetch(`${baseUrl}/api/v1/ingest/file`, {
      method: "POST",
      headers: getHeaders(apiKey, false),
      body,
    });
    if (!response.ok) throw new Error(await errorMessage(response));
    return response.json() as Promise<Record<string, unknown>>;
  },

  deleteDocument: (id: string) =>
    request<{ status: string; message: string }>(
      `/api/v1/documents/${encodeURIComponent(id)}`,
      { method: "DELETE" },
    ),

  listApiKeys: () =>
    request<ApiKeyListResponse>("/api/v1/admin/keys"),

  createApiKey: (payload: CreateApiKeyRequest) =>
    request<CreateApiKeyResponse>("/api/v1/admin/keys", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  revokeApiKey: (displayedKey: string) =>
    request<{ status: string; message: string }>(
      `/api/v1/admin/keys/${encodeURIComponent(displayedKey.replace(/\.\.\.$/, ""))}`,
      { method: "DELETE" },
    ),

  downloadReport: async (path: string, payload?: SearchRequest) => {
    const { baseUrl, apiKey } = getConnection();
    const response = await fetch(`${baseUrl}${path}`, {
      method: payload ? "POST" : "GET",
      headers: getHeaders(apiKey, Boolean(payload)),
      body: payload ? JSON.stringify(payload) : undefined,
    });

    if (!response.ok) throw new Error(await errorMessage(response));

    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filenameFrom(response);
    anchor.click();
    URL.revokeObjectURL(objectUrl);
  },
};
