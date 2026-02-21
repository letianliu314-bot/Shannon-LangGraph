import { proxyJsonRequest } from "@/lib/backend";

interface RouteContext {
  params: { threadId: string };
}

export async function GET(request: Request, context: RouteContext): Promise<Response> {
  const threadId = encodeURIComponent(context.params.threadId);
  const url = new URL(request.url);
  const sinceSeq = url.searchParams.get("since_seq") || "0";
  const limit = url.searchParams.get("limit") || "200";

  return proxyJsonRequest(`/threads/${threadId}/events?since_seq=${encodeURIComponent(sinceSeq)}&limit=${encodeURIComponent(limit)}`);
}
