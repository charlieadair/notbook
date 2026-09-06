import { createContext, useContext, useState, type ReactNode } from "react";
import { createStudyApi, type StudyApi } from "./index";

const ApiContext = createContext<StudyApi | null>(null);

export function ApiProvider({ children, api }: { children: ReactNode; api?: StudyApi }) {
  const [value] = useState(() => api ?? createStudyApi());
  return <ApiContext.Provider value={value}>{children}</ApiContext.Provider>;
}

export function useApi(): StudyApi {
  const api = useContext(ApiContext);
  if (!api) throw new Error("useApi must be used inside ApiProvider");
  return api;
}
