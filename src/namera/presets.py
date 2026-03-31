from __future__ import annotations

TLD_PRESETS: dict[str, list[str]] = {
    "popular": ["com", "net", "org", "io", "co", "dev"],
    "tech": ["com", "io", "dev", "ai", "app", "tech", "cloud", "code"],
    "startup": ["com", "io", "co", "app", "ai", "so", "ly"],
    "cheap": ["xyz", "online", "site", "website", "click", "space", "fun"],
    "premium": ["com", "io", "ai", "app", "dev"],
    "finance": ["com", "io", "finance", "money", "capital", "fund", "co"],
    "design": ["com", "design", "art", "studio", "graphics", "io"],
    "security": ["com", "security", "io", "dev", "network", "systems"],
    "gaming": ["com", "gg", "io", "game", "games", "play", "zone"],
    "social": ["com", "social", "community", "chat", "io", "co"],
    "ecommerce": ["com", "shop", "store", "market", "buy", "io"],
    "education": ["com", "edu", "academy", "courses", "io", "training"],
    "health": ["com", "health", "care", "clinic", "io", "co"],
    "food": ["com", "kitchen", "recipes", "menu", "io", "co"],
    "travel": ["com", "travel", "tours", "holiday", "io", "co"],
    "media": ["com", "media", "news", "press", "io", "co"],
    "creative": ["com", "design", "art", "studio", "works", "io"],
    "geo-us": ["com", "us", "co", "io"],
    "geo-eu": ["com", "eu", "de", "fr", "nl", "io"],
    "geo-asia": ["com", "asia", "jp", "in", "io", "co"],
}


def get_preset(name: str) -> list[str] | None:
    """Get TLDs for a preset name. Returns None if not found."""
    return TLD_PRESETS.get(name.lower())


def get_all_preset_names() -> list[str]:
    """Return sorted list of all preset names."""
    return sorted(TLD_PRESETS.keys())


def resolve_tld_input(tld_input: str) -> list[str]:
    """Resolve a TLD input which can be either a preset name or comma-separated TLDs.

    If the input matches a preset name, returns that preset's TLDs.
    Otherwise treats it as comma-separated TLD list.
    """
    preset = get_preset(tld_input)
    if preset:
        return preset
    return [t.strip().lstrip(".") for t in tld_input.split(",") if t.strip()]
