import { proxyJsonRequest } from "@/lib/backend";

export async function POST(request: Request): Promise<Response> {
  const payload = await request.text();

  return proxyJsonRequest("/runs", {
    method: "POST",
    body: payload,
    headers: {
      "content-type": "application/json"
    }
  });
}
