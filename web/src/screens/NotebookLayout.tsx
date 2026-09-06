import { Link, Outlet, useParams } from "react-router-dom";
import { useApi } from "../api/ApiContext";
import { Banner } from "../components/Banner";
import { StepNav } from "../components/StepNav";
import { useAsync } from "../hooks/useAsync";
import { errorMessage } from "../lib/format";

export function NotebookLayout() {
  const { notebookId = "" } = useParams();
  const api = useApi();
  const notebook = useAsync(() => api.getNotebook(notebookId), [api, notebookId]);

  return (
    <div>
      <div className="topbar">
        <Link className="brand" to="/">
          Notbook <span>/ {notebook.data?.title ?? "notebook"}</span>
        </Link>
        <Link to="/">All notebooks</Link>
      </div>
      <StepNav notebookId={notebookId} />
      {notebook.error ? (
        <Banner tone="error">
          Could not load this notebook. {errorMessage(notebook.error)} <Link to="/">Back home</Link>
        </Banner>
      ) : null}
      <Outlet context={{ notebookId, title: notebook.data?.title ?? "" }} />
    </div>
  );
}
