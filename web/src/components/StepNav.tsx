import { NavLink, useLocation } from "react-router-dom";

const STEPS = [
  { to: "upload", label: "Materials" },
  { to: "vault", label: "Vault" },
  { to: "topics", label: "Topics" },
  { to: "quiz", label: "Pretest" },
  { to: "scoreboard", label: "Scoreboard" },
  { to: "orchestrator", label: "Focus" },
] as const;

export function StepNav({ notebookId }: { notebookId: string }) {
  const location = useLocation();
  const onFocusChat = location.pathname.includes("/chats/");
  return (
    <ol className="steps" aria-label="Study steps">
      {STEPS.map((step) => (
        <li key={step.to}>
          <NavLink
            to={`/notebooks/${notebookId}/${step.to}`}
            className={({ isActive }) =>
              isActive || (step.to === "orchestrator" && onFocusChat) ? "current" : undefined
            }
          >
            {step.label}
          </NavLink>
        </li>
      ))}
    </ol>
  );
}
