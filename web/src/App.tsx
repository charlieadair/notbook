import { Navigate, Route, Routes } from "react-router-dom";
import { Home } from "./screens/Home";
import { NotebookLayout } from "./screens/NotebookLayout";
import { Quiz } from "./screens/Quiz";
import { Scoreboard } from "./screens/Scoreboard";
import { Topics } from "./screens/Topics";
import { Upload } from "./screens/Upload";
import { Vault } from "./screens/Vault";

export function App() {
  return (
    <div className="app-shell">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/notebooks/:notebookId" element={<NotebookLayout />}>
          <Route index element={<Navigate to="upload" replace />} />
          <Route path="upload" element={<Upload />} />
          <Route path="vault" element={<Vault />} />
          <Route path="topics" element={<Topics />} />
          <Route path="quiz" element={<Quiz />} />
          <Route path="scoreboard" element={<Scoreboard />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
