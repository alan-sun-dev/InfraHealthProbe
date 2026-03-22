"""Probe registry — auto-discovers all probe classes."""

from __future__ import annotations

from .base import BaseProbe, ProbeResult, ProbeStatus
from .ping import PingProbe
from .dns import DnsProbe
from .tcp import TcpProbe
from .http import HttpProbe
from .ssh import SshProbe
from .wifi_adapter import WiFiProbeAdapter

# Registry: probe name -> probe class
PROBE_REGISTRY: dict[str, type[BaseProbe]] = {
    "ping": PingProbe,
    "dns": DnsProbe,
    "tcp": TcpProbe,
    "http": HttpProbe,
    "ssh": SshProbe,
    "wifi": WiFiProbeAdapter,
}


def get_probe(name: str) -> BaseProbe:
    """Instantiate a probe by name.

    Args:
        name: Probe name (e.g. 'ping', 'dns', 'tcp', 'http').

    Returns:
        Probe instance.

    Raises:
        KeyError: If probe name is not registered.
    """
    if name not in PROBE_REGISTRY:
        raise KeyError(f"Unknown probe: '{name}'. Available: {list(PROBE_REGISTRY.keys())}")
    return PROBE_REGISTRY[name]()


def list_probes() -> list[str]:
    """Return all registered probe names."""
    return list(PROBE_REGISTRY.keys())
