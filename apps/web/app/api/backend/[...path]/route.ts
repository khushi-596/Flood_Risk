import { NextRequest, NextResponse } from "next/server";

const TARGETS = [
  process.env.INTERNAL_API_URL,
  process.env.NEXT_PUBLIC_API_BASE_URL,
  "http://127.0.0.1:8000/v1",
  "http://localhost:8000/v1",
  "http://flood-risk-api:8000/v1",
  "http://flood-risk-api:10000/v1",
  "https://flood-risk-api-yuhz.onrender.com/v1",
  "https://flood-risk-api.onrender.com/v1",
].filter(Boolean) as string[];

async function forward(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const subpath = path.join("/");
  const search = req.nextUrl.search;

  let body: BodyInit | undefined = undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    body = await req.arrayBuffer();
  }

  const headers: Record<string, string> = {};
  req.headers.forEach((value, key) => {
    // Forward auth, content-type, accept
    const lower = key.toLowerCase();
    if (lower === "authorization" || lower === "content-type" || lower === "accept") {
      headers[key] = value;
    }
  });

  let lastError: Error | null = null;
  let lastStatus = 502;

  // Try each possible backend address
  for (const base of TARGETS) {
    const cleanBase = base.replace(/\/+$/, "");
    const targetUrl = `${cleanBase}/${subpath}${search}`;
    try {
      const response = await fetch(targetUrl, {
        method: req.method,
        headers,
        body,
        cache: "no-store",
      });

      // If we got a valid response (even 4xx/5xx from the actual FastAPI app), return it
      if (response.status !== 502 && response.status !== 503) {
        const resBody = await response.arrayBuffer();
        const resHeaders = new Headers();
        response.headers.forEach((v, k) => {
          if (k.toLowerCase() === "content-type") {
            resHeaders.set(k, v);
          }
        });
        return new NextResponse(resBody, {
          status: response.status,
          headers: resHeaders,
        });
      }
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
    }
  }

  return NextResponse.json(
    {
      detail:
        lastError?.message ||
        "Backend service is starting up or temporarily unavailable. Please retry in a few seconds.",
    },
    { status: lastStatus }
  );
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const PUT = forward;
export const DELETE = forward;
