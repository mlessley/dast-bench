from __future__ import annotations

from .models import CriteriaTaxonomy, Vendor


def gap_report(taxonomy: CriteriaTaxonomy, vendors: list[Vendor]) -> list[str]:
    messages = [f"warning: {issue}" for issue in taxonomy.validate_weights()]
    for vendor in vendors:
        scored_ids = {s.criterion_id for s in vendor.scores}
        missing = [c.id for c in taxonomy.criteria if c.id not in scored_ids]
        if missing:
            messages.append(f"{vendor.id}: missing scores for {', '.join(missing)}")
    return messages
