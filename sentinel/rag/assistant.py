"""Compliance assistant: retrieve -> ground -> answer with citations.

Hard rule: the assistant answers **only** from retrieved passages. If retrieval
returns nothing relevant, it says so rather than answering from model memory --
a confidently wrong regulatory answer is worse than no answer.
"""
from __future__ import annotations

from dataclasses import dataclass

from sentinel.llm.provider import LLMUnavailable, get_llm
from sentinel.rag.store import Chunk, RegulationStore

SYSTEM = (
    "You are an industrial safety compliance assistant for an Indian heavy-industry "
    "plant. Answer ONLY from the provided reference passages. If the passages do not "
    "cover the question, say so plainly and do not speculate. Be concise and direct: "
    "lead with the operational answer (what must happen), then the reasoning. Never "
    "invent clause numbers or quote text that is not in the passages."
)


@dataclass
class ComplianceAnswer:
    question: str
    answer: str
    citations: list[str]
    chunks: list[Chunk]
    backend: str
    grounded: bool

    def as_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.answer,
            "citations": self.citations,
            "backend": self.backend,
            "grounded": self.grounded,
        }


class ComplianceAssistant:
    def __init__(self, store: RegulationStore | None = None, prefer: str | None = None):
        self.store = store or RegulationStore().build()
        self.llm = get_llm(prefer=prefer)

    def ask(self, question: str, k: int = 4) -> ComplianceAnswer:
        chunks = self.store.search(question, k=k)
        citations = []
        seen = set()
        for c in chunks:
            cite = c.citation()
            if cite not in seen:
                seen.add(cite)
                citations.append(cite)

        if not chunks:
            return ComplianceAnswer(
                question=question,
                answer=("No relevant passage was found in the regulation corpus, so I "
                        "cannot answer this from source. Escalate to the safety officer."),
                citations=[], chunks=[], backend=self.llm.backend, grounded=False,
            )

        context = "\n\n".join(
            f"[{i+1}] {c.standard} — {c.section}\n{c.text}" for i, c in enumerate(chunks)
        )
        prompt = (
            f"Reference passages:\n\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer using only the passages above. Cite the passages you rely on by "
            "their standard and section name."
        )

        try:
            answer = self.llm.generate(prompt, system=SYSTEM)
        except LLMUnavailable:
            # extractive degradation: return the source text itself
            top = chunks[0]
            answer = ("[No language model available — returning the most relevant source "
                      f"passage verbatim.]\n\n{top.standard} — {top.section}:\n{top.text}")

        return ComplianceAnswer(
            question=question, answer=answer.strip(), citations=citations,
            chunks=chunks, backend=self.llm.backend, grounded=True,
        )
