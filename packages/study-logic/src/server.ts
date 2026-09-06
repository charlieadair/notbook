import { StudyEngine } from "./engine.js";
import { createStudyServer } from "./http.js";
import { STANDALONE_SMOKE_PORT } from "./ports.js";
import { createFixtureVault, FIXTURE_NOTEBOOK_ID } from "./vault.js";

const port = Number(process.env.PORT ?? STANDALONE_SMOKE_PORT);
const engine = new StudyEngine({ vault: createFixtureVault() });
const server = createStudyServer(engine);

server.listen(port, () => {
  process.stdout.write(
    `study-logic offline smoke on http://127.0.0.1:${port} ` +
      `(fixture notebook: ${FIXTURE_NOTEBOOK_ID}; DEMO API is Backend :8000)\n`,
  );
});
