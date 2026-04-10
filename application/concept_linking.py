from __future__ import annotations

from domain.knowledge import CrossTicketConcept, CrossTicketLink, TicketKnowledgeMap


class ConceptLinkingService:
    def build(self, tickets: list[TicketKnowledgeMap], min_ticket_overlap: int = 2) -> list[CrossTicketConcept]:
        keyword_index: dict[str, set[str]] = {}
        atom_index: dict[str, list[str]] = {}

        for ticket in tickets:
            for atom in ticket.atoms:
                for keyword in atom.keywords:
                    normalized = keyword.strip().lower()
                    if not normalized:
                        continue
                    keyword_index.setdefault(normalized, set()).add(ticket.ticket_id)
                    atom_index.setdefault(normalized, []).append(atom.atom_id)

        concepts: list[CrossTicketConcept] = []
        for keyword, ticket_ids in sorted(keyword_index.items()):
            if len(ticket_ids) < min_ticket_overlap:
                continue
            confidence = min(0.95, 0.55 + 0.1 * len(ticket_ids))
            concepts.append(
                CrossTicketConcept(
                    concept_id=f"concept-{keyword}",
                    label=keyword,
                    normalized_label=keyword,
                    description=f"Concept shared across {len(ticket_ids)} tickets.",
                    ticket_ids=sorted(ticket_ids),
                    atom_ids=atom_index.get(keyword, []),
                    strength=confidence,
                    confidence=confidence,
                )
            )

        concept_map = {concept.concept_id: concept for concept in concepts}
        for ticket in tickets:
            links: list[CrossTicketLink] = []
            for concept in concepts:
                if ticket.ticket_id not in concept.ticket_ids:
                    continue
                related_ticket_ids = [item for item in concept.ticket_ids if item != ticket.ticket_id]
                if not related_ticket_ids:
                    continue
                links.append(
                    CrossTicketLink(
                        concept_id=concept.concept_id,
                        concept_label=concept.label,
                        related_ticket_ids=related_ticket_ids,
                        rationale=f"Shared concept: {concept_map[concept.concept_id].label}",
                        strength=concept.strength,
                    )
                )
            ticket.cross_links_to_other_tickets[:] = links

        return concepts
