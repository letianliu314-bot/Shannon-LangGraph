import { buildOrchestratorUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

interface RouteContext {
  params: { threadId: string };
}

export async function GET(request: Request, context: RouteContext): Promise<Response> {
  const threadId = encodeURIComponent(context.params.threadId);
  const url = new URL(request.url);
  const sinceSeq = url.searchParams.get("since_seq") || "0";

  let upstream: Response;
  try {
    upstream = await fetch(
      buildOrchestratorUrl(
        `/threads/${threadId}/events/stream?since_seq=${encodeURIComponent(sinceSeq)}`
      ),
      {
        method: "GET",
        headers: {
          Accept: "text/event-stream"
        },
        cache: "no-store"
      }
    );
  } catch (error) {
    return Response.json(
      {
        detail: `Upstream orchestrator is unreachable: ${error instanceof Error ? error.message : String(error)}`
      },
      { status: 502 }
    );
  }

  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: {
        "content-type": upstream.headers.get("content-type") || "application/json"
      }
    });
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-transform",
      connection: "keep-alive",
      "x-accel-buffering": "no"
    }
  });
}
