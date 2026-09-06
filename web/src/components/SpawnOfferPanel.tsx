import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApi } from "../api/ApiContext";
import type { Chat, Topic } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { errorMessage } from "../lib/format";
import { capSpawnSelection, defaultSelectedTopicIds, sortSpawnCandidates } from "../lib/spawn";
import { Banner } from "./Banner";

type Props = {
  notebookId: string;
  onAvailability?: (hasOffer: boolean) => void;
};

export function SpawnOfferPanel({ notebookId, onAvailability }: Props) {
  const api = useApi();
  const navigate = useNavigate();
  const offer = useAsync(() => api.getSpawnOffer(notebookId), [api, notebookId]);
  const topics = useAsync(() => api.listTopics(notebookId), [api, notebookId]);
  const chats = useAsync(() => api.listChats(notebookId), [api, notebookId]);
  const [picked, setPicked] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const names = new Map((topics.data ?? []).map((t: Topic) => [t.id, t.name]));
  const openSpecialists = (chats.data ?? []).filter((c: Chat) => c.kind === "specialist" && c.status === "open");
  const openTopicIds = new Set(openSpecialists.flatMap((c: Chat) => c.topic_ids));
  const maxSpawn = offer.data?.max_spawn ?? 2;
  const remaining = Math.max(0, maxSpawn - openSpecialists.length);
  const candidates = useMemo(
    () =>
      sortSpawnCandidates(offer.data?.candidates ?? []).filter((c) => !openTopicIds.has(c.topic_id)),
    [offer.data?.candidates, openSpecialists],
  );
  const selected = picked ?? defaultSelectedTopicIds(candidates, remaining);
  const hasOffer = candidates.length > 0 && remaining > 0;

  useEffect(() => {
    if (offer.loading) return;
    onAvailability?.(hasOffer);
  }, [hasOffer, offer.loading, onAvailability]);

  if (offer.loading) return null;

  if (offer.error) {
    return (
      <p className="muted">
        Focus chats unavailable ({errorMessage(offer.error)}). Scoreboard above is still the source of truth.
      </p>
    );
  }

  if (openSpecialists.length > 0 && !hasOffer) {
    return (
      <section className="paper">
        <h2>Focus chats</h2>
        <p className="muted">Open specialist chats stay scoped. The orchestrator keeps the holistic map.</p>
        <div className="row">
          <Link className="btn btn-primary" to={`/notebooks/${notebookId}/orchestrator`}>
            Open orchestrator
          </Link>
        </div>
      </section>
    );
  }

  if (!hasOffer) return null;

  function toggle(topicId: string) {
    setPicked((prev) => {
      const current = prev ?? defaultSelectedTopicIds(candidates, remaining);
      if (current.includes(topicId)) return current.filter((id) => id !== topicId);
      return capSpawnSelection([...current, topicId], remaining);
    });
  }

  async function openFocus() {
    const topicIds = capSpawnSelection(selected, remaining);
    if (!topicIds.length) {
      setError("Pick at least one topic — or skip and stay on the scoreboard.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await api.createSpecialists(notebookId, topicIds);
      if (!created.chats.length) {
        setError("Study-logic did not return a specialist chat. S1 routes may not be mounted yet.");
        return;
      }
      navigate(`/notebooks/${notebookId}/chats/${created.chats[0].id}`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="paper" aria-labelledby="spawn-offer-heading">
      <h2 id="spawn-offer-heading">Focus chats (offer)</h2>
      <p className="lede">
        You have gaps worth a specialist. I will keep the broad map here and handle lighter gaps.         Default at most {maxSpawn} open specialist chats — this is an offer, not an automatic
        explosion of windows. Selected topics open as{" "}
        <strong>one</strong> focus chat{remaining < maxSpawn ? ` (${remaining} slot left)` : ""}.
      </p>
      <div className="choices" role="group" aria-label="Suggested focus topics">
        {candidates.map((candidate) => {
          const checked = selected.includes(candidate.topic_id);
          const name = names.get(candidate.topic_id) ?? candidate.topic_id;
          return (
            <label key={candidate.topic_id} className="choice">
              <input
                type="checkbox"
                checked={checked}
                onChange={() => toggle(candidate.topic_id)}
              />
              <span>
                <strong>{name}</strong>{" "}
                <span className={`badge badge-${candidate.severity}`}>{candidate.severity}</span>
                <div className="muted">{candidate.reason}</div>
              </span>
            </label>
          );
        })}
      </div>
      {error ? <Banner tone="error">{error}</Banner> : null}
      <div className="row">
        <button className="btn btn-primary" type="button" onClick={() => void openFocus()} disabled={busy || selected.length === 0}>
          {busy ? "Opening…" : selected.length ? "Open focus chat" : "Open focus chat"}
        </button>
        <Link className="btn btn-ghost" to={`/notebooks/${notebookId}/orchestrator`}>
          Skip — keep scoreboard
        </Link>
      </div>
    </section>
  );
}
