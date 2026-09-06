import type { ReactNode } from "react";

type Tone = "info" | "error" | "ok";

export function Banner({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: Tone;
}) {
  const cls = tone === "error" ? "banner banner-error" : tone === "ok" ? "banner banner-ok" : "banner";
  return (
    <div className={cls} role={tone === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}
