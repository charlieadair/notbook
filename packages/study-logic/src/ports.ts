/** DEMO Web UI. Study-logic must not bind this port. */
export const DEMO_UI_PORT = 3000;

/** DEMO single API. Backend FastAPI mounts `/api/v1` study routes here. */
export const DEMO_BACKEND_PORT = 8000;

/** Fixture/offline smoke binds this host (never all interfaces). */
export const STANDALONE_SMOKE_HOST = "127.0.0.1";

/** Offline fixture smoke server only (`npm start` / PORT). */
export const STANDALONE_SMOKE_PORT = 3001;
