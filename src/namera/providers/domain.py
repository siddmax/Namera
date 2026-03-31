from __future__ import annotations

import asyncio
import socket

from namera.providers.base import Availability
from namera.retry import with_retry


class DnsLookupUtil:
    """DNS resolution utility — used as fallback by RdapProvider."""

    @staticmethod
    @with_retry(max_retries=2, initial_backoff=0.5)
    async def resolve(domain: str) -> Availability:
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, socket.gethostbyname, domain)
            return Availability.TAKEN
        except socket.gaierror as e:
            if e.errno in (socket.EAI_NONAME, 8, -2, -5):
                return Availability.AVAILABLE
            raise
        except (socket.timeout, OSError):
            raise
