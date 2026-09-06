import { NavLink } from "react-router-dom";

const STEPS = [
  { to: "upload", label: "Materials" },
  { to: "vault", label: "Vault" },
  { to: "topics", label: "Topics" },
  { to: "quiz", label: "Pretest" },
  { to: "scoreboard", label: "Scoreboard" },
] as const;

export function StepNav({ notebookId }: { notebookId: string }) {
  return (
    <ol className="steps" aria-label="Study steps">
      {STEPS.map((step) => (
        <li key={step.to}>
          <NavLink
            to={`/notebooks/${notebookId}/${step.to}`}
            className={({ isActive }) => (isActive ? "current" : undefined)}
          >
            {step.label}
          </NavLink>
        </li>
      ))}
    </ol>
  );
}
