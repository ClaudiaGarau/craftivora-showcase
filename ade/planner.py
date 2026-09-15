from __future__ import annotations

from .types import Plan, WorkItem


def classify(objective: str) -> str:
    text = objective.lower()
    if any(k in text for k in ("video", "presentazione", "presentation", "slide", "immagine pubblicitaria", "creative")):
        return "media"
    if any(k in text for k in ("etsy", "amazon", "affiliate", "marketplace", "listing", "seo", "pdf", "prodotto digitale")):
        return "commerce"
    if any(k in text for k in ("saas", "app", "api", "website", "sito", "automation", "codice", "deploy", "eseguibile", ".exe")):
        return "software"
    if any(k in text for k in ("facebook", "meta", "google ads", "campaign", "campagna")):
        return "marketing"
    return "general"


def make_plan(objective: str) -> Plan:
    domain = classify(objective)
    items = [WorkItem("atena", "Research evidence, constraints, current state and alternatives", ["web", "files"], "research")]
    if domain == "commerce":
        items.append(WorkItem("poseidone", "Audit product, offer, marketplace fit, files, SEO and publication requirements", ["inspect_pdf", "inspect_zip", "inspect_image"], "general", [0]))
    tools = ["filesystem", "code", "image"]
    if domain == "media":
        tools += ["presentation", "video", "render"]
    if domain == "software":
        tools += ["tests", "build", "deploy"]
    items.append(WorkItem("apollo", "Create the requested artifacts or implementation using verified requirements", tools, "creation", list(range(len(items)))))
    items.append(WorkItem("argo", "Independently verify accuracy, safety, regressions, visual quality and release readiness", ["tests", "render", "policy"], "qa", list(range(len(items)))))
    return Plan(objective=objective, domain=domain, items=items, assumptions=[])
