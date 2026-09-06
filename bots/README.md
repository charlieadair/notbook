# Notbook — Grok Bot roster (challenge)

Specialized teammates that build **S0** of [`SPEC.md`](../SPEC.md). Not a linear task list: each Bot has one job, standing rules, and a starter task you paste into [Grok Bot](https://docs.x.ai/grok-bot/overview).

## Roster

| Bot | File | Job |
| --- | --- | --- |
| **Scope** | [`scope.md`](scope.md) | Owns SPEC truth; rejects scope creep; S0 vs later |
| **Study-logic** | [`study-logic.md`](study-logic.md) | Topics, quiz engine, scoreboard, (S1) chat tree prompts |
| **Backend** | [`backend.md`](backend.md) | Ingest, OCR, vault, retrieve, inference adapter, local API |
| **Web** | [`web.md`](web.md) | UI: upload, vault browser, quiz player, citations, scoreboard |
| **Release** | [`release.md`](release.md) | Merge/ship gate, smoke checks, keep demo green |

**Deferred (not created for challenge):** Legal, hosted DevOps / k8s / Cloudflare, multi-tenant Security.

## How to use in Grok Bot

1. Create five Bots (New → Create new agent → Edit Profile).  
2. Paste **Name / Title / Description** from each file into the profile.  
3. Paste **Standing rules** into the first message (or pin as the Bot’s working charter).  
4. Put all five in one **group chat** named e.g. `Notbook S0` so handoffs are visible.  
5. Give each Bot its **Starter task** only after Scope confirms the repo is cloned and `SPEC.md` is the contract.  
6. Run `grok inspect` / read the profile docs if you also use Grok Build CLI locally — same `SPEC.md` applies.

## Handoff rules (all Bots)

- **Source of truth:** `SPEC.md`. If a request conflicts with S0, stop and ask Scope (or Charlie).  
- **Files over vibes:** propose or write concrete paths; link PRs/commits in the group chat.  
- **No secrets in chat profiles:** API keys, kubeconfigs, GHCR tokens stay in env/secret stores — never in Bot description text.  
- **Shared computer warning:** all Grok Bots share one cloud VM; do not treat Bots as security isolation.  
- **Challenge bar:** demo must show inspectable vault + grounded pretest + scoreboard on self-hosted stack.

## Suggested group kickoff (Charlie → group)

```text
We are building Notbook for the Student Build Challenge.
Contract: SPEC.md (S0 only). Profiles: bots/*.md.
Scope owns priority. Release owns merge. Others implement in parallel against agreed interfaces.
First: Scope posts the S0 interface sketch Backend/Web/Study-logic must share; then specialists start.
```
