from __future__ import annotations

from namera.providers.base import Availability, CheckType, Provider, ProviderResult


class StubTrademarkProvider(Provider):
    """Stub trademark lookup — replace with a real API (e.g., USPTO, EUIPO) when ready."""

    name = "trademark-stub"
    check_type = CheckType.TRADEMARK

    async def check(self, query: str, **kwargs) -> ProviderResult:
        return ProviderResult(
            check_type=CheckType.TRADEMARK,
            provider_name=self.name,
            query=query,
            available=Availability.UNKNOWN,
            details={"note": "Stub provider — no real API configured yet."},
        )
