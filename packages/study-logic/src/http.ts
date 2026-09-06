import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import { StudyError } from "./errors.js";
import type { StudyEngine } from "./engine.js";

type Route = {
  method: string;
  pattern: RegExp;
  handler: (ctx: RouteContext) => Promise<unknown> | unknown;
};

type RouteContext = {
  engine: StudyEngine;
  params: string[];
  body: unknown;
};

const API_PREFIX = "/api/v1";

function path(pattern: string): RegExp {
  return new RegExp(`^(?:${API_PREFIX})?${pattern}$`);
}

export function createStudyServer(engine: StudyEngine): Server {
  const routes: Route[] = [
    {
      method: "GET",
      pattern: path("/health"),
      handler: () => ({ ok: true, service: "study-logic" }),
    },
    {
      method: "POST",
      pattern: path("/notebooks/([^/]+)/topics/propose"),
      handler: ({ engine, params }) => engine.proposeTopics(params[0]),
    },
    {
      method: "POST",
      pattern: path("/notebooks/([^/]+)/topics/confirm"),
      handler: ({ engine, params, body }) => {
        const input = asObject(body);
        return engine.confirmTopics(params[0], {
          names: asStringArray(input.names),
          topic_ids: asStringArray(input.topic_ids),
        });
      },
    },
    {
      method: "GET",
      pattern: path("/notebooks/([^/]+)/topics"),
      handler: ({ engine, params }) => engine.listTopics(params[0]),
    },
    {
      method: "POST",
      pattern: path("/notebooks/([^/]+)/quizzes"),
      handler: ({ engine, params }) => engine.createQuiz(params[0]),
    },
    {
      method: "POST",
      pattern: path("/quizzes/([^/]+)/attempts"),
      handler: ({ engine, params, body }) => {
        const input = asObject(body);
        return engine.gradeAttempt(params[0], {
          item_id: String(input.item_id ?? ""),
          selected_choice_id: String(input.selected_choice_id ?? ""),
        });
      },
    },
    {
      method: "GET",
      pattern: path("/notebooks/([^/]+)/scoreboard"),
      handler: ({ engine, params }) => engine.scoreboard(params[0]),
    },
  ];

  return createServer(async (req, res) => {
    try {
      const url = new URL(req.url ?? "/", "http://localhost");
      const method = (req.method ?? "GET").toUpperCase();
      const route = routes.find((r) => r.method === method && r.pattern.test(url.pathname));
      if (!route) {
        sendJson(res, 404, { error: "NotFound", message: `No route for ${method} ${url.pathname}` });
        return;
      }
      const match = url.pathname.match(route.pattern);
      const params = match?.slice(1) ?? [];
      const body = await readJson(req);
      const result = await route.handler({ engine, params, body });
      sendJson(res, 200, result);
    } catch (err) {
      if (err instanceof StudyError) {
        sendJson(res, err.status, err.toJSON());
        return;
      }
      const message = err instanceof Error ? err.message : "Internal error";
      sendJson(res, 500, { error: "InternalError", message });
    }
  });
}

function asObject(body: unknown): Record<string, unknown> {
  return body && typeof body === "object" && !Array.isArray(body)
    ? (body as Record<string, unknown>)
    : {};
}

function asStringArray(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) return undefined;
  return value.map((v) => String(v));
}

async function readJson(req: IncomingMessage): Promise<unknown> {
  const method = (req.method ?? "GET").toUpperCase();
  if (method === "GET" || method === "HEAD") return undefined;

  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    chunks.push(typeof chunk === "string" ? Buffer.from(chunk) : chunk);
  }
  if (chunks.length === 0) return undefined;
  const raw = Buffer.concat(chunks).toString("utf8").trim();
  if (!raw) return undefined;
  return JSON.parse(raw) as unknown;
}

function sendJson(res: ServerResponse, status: number, body: unknown): void {
  const json = JSON.stringify(body);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(json),
  });
  res.end(json);
}
