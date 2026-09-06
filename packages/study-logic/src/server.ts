import { StudyEngine } from "./engine.js";
import { createStudyServer } from "./http.js";
import { STANDALONE_SMOKE_HOST, STANDALONE_SMOKE_PORT } from "./ports.js";
import { createFixtureVault, FIXTURE_NOTEBOOK_ID } from "./vault.js";

const host = process.env.HOST ?? STANDALONE_SMOKE_HOST;
const port = Number(process.env.PORT ?? STANDALONE_SMOKE_PORT);
const engine = new StudyEngine({ vault: createFixtureVault() });
const server = createStudyServer(engine);

server.listen(port, host, () => {
  process.stdout.write(
    `study-logic offline smoke on http://${host}:${port} ` +
      `(loopback only; DEMO API is Backend FastAPI :8000 /api/v1)\n`,
  );
});
