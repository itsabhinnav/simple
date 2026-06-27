"""Natural-language assistant service.

Loads requirements / test cases / design tickets / specs from the existing
domain services, ranks them by lexical overlap with the user question, builds
a compact JSON context block, and asks the configured LLM provider to answer
with explicit ID citations.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Sequence, Set, Tuple

from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


# Words that contribute nothing to retrieval ranking. Kept tiny so the
# scoring stays cheap; the goal is to filter "is", "the", "for", "any" out
# of questions like "is there any requirement for BT disconnection?".
_STOPWORDS: Set[str] = {
    "a", "an", "and", "any", "are", "as", "at", "be", "by", "do", "does",
    "for", "from", "has", "have", "how", "i", "in", "is", "it", "list",
    "many", "me", "of", "on", "or", "show", "tell", "that", "the", "there",
    "to", "us", "what", "when", "where", "which", "who", "why", "with",
    "you", "your", "yes", "no", "please", "can", "could", "would", "should",
    "give", "find", "search", "all",
}

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-./]*")


def _tokenize(text: Optional[str]) -> List[str]:
    if not text:
        return []
    return [t.lower() for t in _TOKEN_RE.findall(str(text))]


def _meaningful_terms(question: str) -> List[str]:
    """Strip stopwords; keep short acronyms like 'bt', 'gps', 'p1'."""
    return [t for t in _tokenize(question) if t not in _STOPWORDS]


@dataclass
class Citation:
    kind: str       # 'requirement' | 'test_case' | 'design_ticket' | 'spec'
    id: str         # canonical business id (REQ-001, TC-001, ...)
    title: str
    route: str      # frontend route the chip should navigate to
    score: float


@dataclass
class AssistantContext:
    requirements: List[Dict[str, Any]]
    test_cases: List[Dict[str, Any]]
    design_tickets: List[Dict[str, Any]]
    specs: List[Dict[str, Any]]
    citations: List[Citation]
    matched_terms: List[str]


class AssistantService:
    """Retrieval + prompt assembly + LLM dispatch for the chat assistant."""

    MAX_PER_KIND = 8
    MAX_TOTAL = 24

    def __init__(
        self,
        *,
        requirement_service,
        test_case_service,
        design_ticket_service,
        spec_service,
        vlm_registry,
        vector_index_service=None,
    ) -> None:
        self._requirements = requirement_service
        self._test_cases = test_case_service
        self._design_tickets = design_ticket_service
        self._specs = spec_service
        self._registry = vlm_registry
        self._vector = vector_index_service

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def _safe_call(self, fn, default):
        try:
            return fn() or default
        except Exception as exc:  # noqa: BLE001 - assistant must not crash
            logger.warning(f"Assistant retrieval call failed: {exc}")
            return default

    def _score_row(self, terms: Sequence[str], row: Dict[str, Any], fields: Sequence[str]) -> Tuple[float, List[str]]:
        if not terms:
            return 0.0, []
        haystack = " \n ".join(str(row.get(f, "") or "") for f in fields).lower()
        if not haystack.strip():
            return 0.0, []
        hits: List[str] = []
        score = 0.0
        for term in terms:
            if not term:
                continue
            # Phrase / multi-token term matches (e.g. "bt disconnection") get higher weight
            occurrences = haystack.count(term)
            if occurrences > 0:
                score += occurrences * (3.0 if len(term) <= 3 else 2.0)
                hits.append(term)
        return score, hits

    # ------------------------------------------------------------------
    # Rank fusion helpers (Reciprocal Rank Fusion — RRF)
    # ------------------------------------------------------------------
    @staticmethod
    def _rrf_score(rank: int, k: int = 60) -> float:
        return 1.0 / (k + rank)

    def _kind_to_singular(self, kind: str) -> str:
        return {
            "requirements": "requirement",
            "test_cases": "test_case",
            "design_tickets": "design_ticket",
            "specs": "spec",
        }.get(kind, kind)

    def _kind_to_plural(self, kind: str) -> str:
        return {
            "requirement": "requirements",
            "test_case": "test_cases",
            "design_ticket": "design_tickets",
            "spec": "specs",
        }.get(kind, kind)

    def _collect(self, question: str, kinds: Set[str]) -> AssistantContext:
        terms = _meaningful_terms(question)
        logger.info(f"Assistant retrieval terms: {terms}")

        # ---- 1. Lexical rankings (per kind) ----------------------------
        lexical_rankings: Dict[str, List[Tuple[str, Dict[str, Any], float]]] = {}
        source_meta = {
            "requirements": dict(
                list_fn=self._requirements.get_all_requirements,
                fields=["requirement_id", "title", "description", "tags", "given", "when_action", "then_result", "priority"],
                kind="requirement", id_field="requirement_id", title_field="title",
                route_fn=lambda r: f"/requirements/{r.get('id')}" if r.get("id") else "/requirements",
            ),
            "test_cases": dict(
                list_fn=self._test_cases.get_all_test_cases,
                fields=["test_case_id", "test_objective", "feature", "associated_requirement_id", "tags", "priority", "test_type", "preconditions", "test_steps", "expected_result"],
                kind="test_case", id_field="test_case_id", title_field="test_objective",
                route_fn=lambda r: f"/test-cases/{r.get('test_case_id')}" if r.get("test_case_id") else "/test-cases",
            ),
            "design_tickets": dict(
                list_fn=self._design_tickets.get_all_design_tickets,
                fields=["design_ticket_id", "title", "description", "design_type", "diagram_type", "linked_requirement_id", "tags", "priority", "status"],
                kind="design_ticket", id_field="design_ticket_id", title_field="title",
                route_fn=lambda r: f"/design-tickets/{r.get('id')}" if r.get("id") else "/design-tickets",
            ),
            "specs": dict(
                list_fn=self._specs.get_all_specs,
                fields=["spec_id", "title", "project", "tags", "category", "version", "status"],
                kind="spec", id_field="spec_id", title_field="title",
                route_fn=lambda r: "/specs",
            ),
        }

        all_rows: Dict[Tuple[str, str], Dict[str, Any]] = {}  # (kind, business_id) -> row
        row_meta: Dict[Tuple[str, str], Dict[str, Any]] = {}  # display info

        for plural in ("requirements", "test_cases", "design_tickets", "specs"):
            if plural not in kinds:
                continue
            meta = source_meta[plural]
            rows = self._safe_call(meta["list_fn"], [])
            scored: List[Tuple[float, Dict[str, Any], List[str]]] = []
            for row in rows:
                bid = str(row.get(meta["id_field"]) or row.get("id") or "")
                if not bid:
                    continue
                all_rows[(meta["kind"], bid)] = row
                row_meta[(meta["kind"], bid)] = {
                    "title": str(row.get(meta["title_field"]) or row.get("test_objective") or "(untitled)"),
                    "route": meta["route_fn"](row),
                }
                score, _hits = self._score_row(terms, row, meta["fields"])
                if score > 0:
                    scored.append((score, row, []))
            scored.sort(key=lambda x: x[0], reverse=True)
            ranking: List[Tuple[str, Dict[str, Any], float]] = []
            for rank, (score, row, _) in enumerate(scored[: self.MAX_PER_KIND * 2]):
                bid = str(row.get(meta["id_field"]) or row.get("id") or "")
                ranking.append((bid, row, score))
            lexical_rankings[meta["kind"]] = ranking

        # ---- 2. Vector ranking (across kinds) --------------------------
        vector_hits: List[Any] = []
        vector_used = False
        singular_kinds = {self._kind_to_singular(k) for k in kinds}
        if self._vector is not None:
            try:
                vector_hits = self._vector.search(
                    question,
                    top_k=self.MAX_TOTAL,
                    kinds=list(singular_kinds),
                )
                vector_used = bool(vector_hits)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Vector search failed, lexical only: {exc}")
                vector_hits = []

        # Make any vector-only rows visible even if the row never appeared
        # in the lexical scoring path (e.g. semantic-only match).
        for hit in vector_hits:
            key = (hit.kind, hit.business_id)
            if key not in all_rows:
                # Fetch a minimal projection so the prompt has at least the
                # title/snippet. We do this lazily by re-pulling from the
                # source list once.
                plural = self._kind_to_plural(hit.kind)
                meta = source_meta.get(plural)
                if not meta:
                    continue
                for r in self._safe_call(meta["list_fn"], []):
                    if str(r.get(meta["id_field"]) or r.get("id") or "") == hit.business_id:
                        all_rows[key] = r
                        row_meta[key] = {"title": hit.title or "(untitled)", "route": hit.route or meta["route_fn"](r)}
                        break

        # ---- 3. RRF fusion across signals ------------------------------
        fused: Dict[Tuple[str, str], float] = {}
        for kind_singular, ranking in lexical_rankings.items():
            for rank, (bid, _row, _score) in enumerate(ranking):
                key = (kind_singular, bid)
                fused[key] = fused.get(key, 0.0) + self._rrf_score(rank)
        for rank, hit in enumerate(vector_hits):
            key = (hit.kind, hit.business_id)
            # Vector signal weighted slightly higher so semantic-only matches
            # still surface above weak lexical matches.
            fused[key] = fused.get(key, 0.0) + 1.5 * self._rrf_score(rank)

        # ---- 4. Materialize per-kind kept rows + citations -------------
        ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
        kept_by_kind: Dict[str, List[Dict[str, Any]]] = {"requirement": [], "test_case": [], "design_ticket": [], "spec": []}
        citations: List[Citation] = []
        for (kind_singular, bid), score in ordered:
            if kind_singular not in kept_by_kind:
                continue
            if len(kept_by_kind[kind_singular]) >= self.MAX_PER_KIND:
                continue
            row = all_rows.get((kind_singular, bid))
            if not row:
                continue
            kept_by_kind[kind_singular].append(row)
            meta = row_meta.get((kind_singular, bid), {})
            citations.append(Citation(
                kind=kind_singular,
                id=bid,
                title=meta.get("title", "(untitled)"),
                route=meta.get("route", ""),
                score=round(score, 4),
            ))
            if len(citations) >= self.MAX_TOTAL:
                break

        # Stash retrieval mode for the response payload via a sneaky list attr
        ctx = AssistantContext(
            requirements=kept_by_kind["requirement"],
            test_cases=kept_by_kind["test_case"],
            design_tickets=kept_by_kind["design_ticket"],
            specs=kept_by_kind["spec"],
            citations=citations,
            matched_terms=list(terms),
        )
        ctx.retrieval_mode = "hybrid" if vector_used and lexical_rankings else ("vector" if vector_used else "lexical")  # type: ignore[attr-defined]
        return ctx

    # ------------------------------------------------------------------
    # Prompt assembly
    # ------------------------------------------------------------------
    @staticmethod
    def _slim(row: Dict[str, Any], fields: Sequence[str]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for f in fields:
            v = row.get(f)
            if v in (None, "", []):
                continue
            if isinstance(v, str) and len(v) > 600:
                v = v[:600] + "..."
            out[f] = v
        return out

    def _build_prompt(self, ctx: AssistantContext) -> Tuple[str, Dict[str, Any]]:
        payload = {
            "requirements": [
                self._slim(r, ["requirement_id", "title", "description", "priority", "tags", "given", "when_action", "then_result"])
                for r in ctx.requirements
            ],
            "test_cases": [
                self._slim(t, ["test_case_id", "test_objective", "feature", "associated_requirement_id", "priority", "test_type", "preconditions", "test_steps", "expected_result"])
                for t in ctx.test_cases
            ],
            "design_tickets": [
                self._slim(d, ["design_ticket_id", "title", "description", "design_type", "linked_requirement_id", "priority", "status"])
                for d in ctx.design_tickets
            ],
            "specs": [
                self._slim(s, ["spec_id", "title", "tags", "category", "version", "status"])
                for s in ctx.specs
            ],
        }
        system = (
            "You are Sakura Search, the QA knowledge assistant for Sakura. Answer the user's question using ONLY the JSON facts "
            "provided in the next user message. If the answer is not supported by the data, say so explicitly. "
            "When you reference an item, cite its ID inline in square brackets (e.g. [REQ-014], [TC-007]). "
            "Be concise: 1-2 short paragraphs, then optionally a bullet list of the matching items. "
            "Never invent IDs that do not appear in the facts."
        )
        return system, payload

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------
    def _normalize_kinds(self, kinds: Optional[Sequence[str]]) -> Set[str]:
        default = {"requirements", "test_cases", "design_tickets", "specs"}
        if not kinds:
            return default
        wanted = {str(k).lower().strip() for k in kinds if k}
        return wanted & default or default

    def _resolve_provider(self, provider_name: Optional[str]):
        try:
            return self._registry.get(provider_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Falling back to default provider — requested '{provider_name}' failed: {exc}")
            try:
                return self._registry.get(None)
            except Exception as inner:  # noqa: BLE001
                logger.warning(f"No LLM provider available: {inner}")
                return None

    @staticmethod
    def _retrieval_only_answer(ctx: AssistantContext) -> str:
        if not ctx.citations:
            return "No matching items were found in the selected sources."
        lines = ["Here are the matching items I found:"]
        for citation in ctx.citations[:12]:
            lines.append(f"- [{citation.id}] {citation.title}")
        if len(ctx.citations) > 12:
            lines.append(f"- …and {len(ctx.citations) - 12} more (see Sources below)")
        return "\n".join(lines)

    def answer(
        self,
        question: str,
        *,
        history: Optional[List[Dict[str, str]]] = None,
        kinds: Optional[Sequence[str]] = None,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        question = (question or "").strip()
        if not question:
            raise ValueError("Question is required")

        ctx = self._collect(question, self._normalize_kinds(kinds))
        system, facts = self._build_prompt(ctx)
        prov = self._resolve_provider(provider)
        provider_name = prov.name() if prov is not None else "retrieval"

        messages: List[Dict[str, Any]] = []
        for turn in (history or [])[-6:]:
            role = turn.get("role")
            content = (turn.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        messages.append({
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                f"Facts (JSON):\n{json.dumps(facts, ensure_ascii=False)}"
            ),
        })

        if prov is None:
            answer = self._retrieval_only_answer(ctx)
        else:
            try:
                answer = prov.chat_text(messages, system=system)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"LLM chat_text failed via {prov.name()}: {exc}")
                answer = self._retrieval_only_answer(ctx)

        return {
            "answer": answer.strip() if isinstance(answer, str) else str(answer),
            "provider": provider_name,
            "retrieval_mode": getattr(ctx, "retrieval_mode", "lexical"),
            "citations": [c.__dict__ for c in ctx.citations],
            "matched_terms": ctx.matched_terms,
            "context_counts": {
                "requirements": len(ctx.requirements),
                "test_cases": len(ctx.test_cases),
                "design_tickets": len(ctx.design_tickets),
                "specs": len(ctx.specs),
            },
        }

    def answer_stream(
        self,
        question: str,
        *,
        history: Optional[List[Dict[str, str]]] = None,
        kinds: Optional[Sequence[str]] = None,
        provider: Optional[str] = None,
    ) -> Iterator[Tuple[str, Dict[str, Any]]]:
        """Yields ``(event_name, payload)`` tuples for SSE serialization.

        Event sequence:
          ``meta``  -> citations + matched terms (sent before any tokens).
          ``token`` -> incremental text chunks from the model.
          ``done``  -> empty payload signalling end of stream.
        """
        question = (question or "").strip()
        if not question:
            raise ValueError("Question is required")

        ctx = self._collect(question, self._normalize_kinds(kinds))
        system, facts = self._build_prompt(ctx)
        prov = self._resolve_provider(provider)
        provider_name = prov.name() if prov is not None else "retrieval"

        yield "meta", {
            "provider": provider_name,
            "retrieval_mode": getattr(ctx, "retrieval_mode", "lexical"),
            "citations": [c.__dict__ for c in ctx.citations],
            "matched_terms": ctx.matched_terms,
            "context_counts": {
                "requirements": len(ctx.requirements),
                "test_cases": len(ctx.test_cases),
                "design_tickets": len(ctx.design_tickets),
                "specs": len(ctx.specs),
            },
        }

        messages: List[Dict[str, Any]] = []
        for turn in (history or [])[-6:]:
            role = turn.get("role")
            content = (turn.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        messages.append({
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                f"Facts (JSON):\n{json.dumps(facts, ensure_ascii=False)}"
            ),
        })

        if prov is None:
            yield "token", {"text": self._retrieval_only_answer(ctx)}
        else:
            try:
                for chunk in prov.chat_text_stream(messages, system=system):
                    if chunk:
                        yield "token", {"text": chunk}
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"LLM stream failed via {prov.name()}: {exc}")
                yield "token", {"text": self._retrieval_only_answer(ctx)}

        yield "done", {}
