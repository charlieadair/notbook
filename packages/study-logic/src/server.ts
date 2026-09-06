import { StudyEngine } from "./engine.js";
import { createStudyServer } from "./http.js";
import { createFixtureVault, FIXTURE_NOTEBOOK_ID } from "./vault.js";

const port = Number(process.env.PORT ?? 3000);
const engine = new StudyEngine({ vault: createFixtureVault() });
const server = createStudyServer(engine);

server.listen(port, () => {
  process.stdout.write(
    `study-logic listening on http://127.0.0.1:${port} (fixture notebook: ${FIXTURE_NOTEBOOK_ID})\n`,
  );
});
