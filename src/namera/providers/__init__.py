import importlib
import pkgutil

from namera.providers.base import Provider, ProviderResult, registry

__all__ = ["Provider", "ProviderResult", "registry", "register_all"]


def register_all():
    """Import all provider modules to trigger __init_subclass__ registration.

    New .py files in the providers package auto-register without manual imports.
    """
    for info in pkgutil.walk_packages(__path__, prefix=__name__ + "."):
        importlib.import_module(info.name)
