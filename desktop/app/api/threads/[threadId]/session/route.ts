import { proxyJsonRequest } from "@/lib/backend";

interface RouteContext {
  params: { threadId: string };
}

export async function GET(_request: Request, context: RouteContext): Promise<Response> {
  const threadId = encodeURIComponent(context.params.threadId);
  return proxyJsonRequest(`/threads/${threadId}/session`);
}
