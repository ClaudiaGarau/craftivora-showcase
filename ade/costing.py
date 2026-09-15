from __future__ import annotations

from dataclasses import asdict, dataclass

from .planner import classify


@dataclass(frozen=True)
class CostEstimate:
    domain: str
    quality: str
    model_route: str
    gpu_minutes_low: float
    gpu_minutes_high: float
    cost_usd_low: float
    cost_usd_high: float
    requires_confirmation: bool
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def estimate(objective: str, runtime: dict, quality: str = "auto") -> CostEstimate:
    domain = classify(objective)
    text = objective.lower()
    if quality == "auto":
        quality = "high" if domain in {"media", "software", "commerce"} or any(
            word in text for word in ("verifica", "correggi", "pubblica", "produzione", "fedele")
        ) else "economy"

    profiles = runtime.get("cost_profiles", {})
    profile_name = {
        "media": "video" if "video" in text else "image",
        "commerce": "document",
        "software": "software",
    }.get(domain, "reasoning" if quality == "high" else "fast")
    profile = profiles.get(profile_name, profiles.get("reasoning", {}))
    minutes = profile.get("gpu_minutes", [1.0, 4.0])
    route = profile.get("route", "reasoning" if quality == "high" else "fast")
    low, high = float(minutes[0]), float(minutes[1])
    operator_cost = profile.get("operator_cost_usd", [0.0, 0.0])
    cost_low, cost_high = float(operator_cost[0]), float(operator_cost[1])
    notes = list(profile.get("notes", []))
    notes.append("Stima dei soli operatori/API; l'infrastruttura RunPod è esclusa.")
    return CostEstimate(
        domain=domain,
        quality=quality,
        model_route=route,
        gpu_minutes_low=low,
        gpu_minutes_high=high,
        cost_usd_low=round(cost_low, 4),
        cost_usd_high=round(cost_high, 4),
        requires_confirmation=high >= float(runtime.get("approval", {}).get("confirm_gpu_minutes", 2.0)),
        notes=notes,
    )
