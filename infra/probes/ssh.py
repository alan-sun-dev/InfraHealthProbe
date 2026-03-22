"""SSH reachability probe — tests TCP connection to SSH port."""

from __future__ import annotations

import socket
import time

from .base import BaseProbe, ProbeResult, ProbeStatus


class SshProbe(BaseProbe):
    """Probe SSH reachability by connecting to port 22 and reading the banner."""

    @property
    def name(self) -> str:
        return "ssh"

    @property
    def timeout_ms(self) -> int:
        return 5000

    @property
    def expected_fields(self) -> list[str]:
        return ["latency_ms", "banner"]

    def probe(self, target: dict) -> ProbeResult:
        host = target.get("FQDN") or target.get("IPAddress") or target.get("Hostname", "")
        if not host:
            return ProbeResult(
                probe_name=self.name,
                target_id=target.get("TargetId", "unknown"),
                status=ProbeStatus.ERROR,
                error="No host address available",
            )

        # Use port 22 by default; check if 22 is in target's port list
        port = 22

        start = time.perf_counter()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout_ms / 1000)
            sock.connect((host, port))
            elapsed_ms = (time.perf_counter() - start) * 1000

            # Try to read SSH banner (e.g. "SSH-2.0-OpenSSH_8.9")
            banner = ""
            try:
                sock.settimeout(2.0)
                data = sock.recv(256)
                banner = data.decode("utf-8", errors="replace").strip()
            except (socket.timeout, OSError):
                pass
            finally:
                sock.close()

            return ProbeResult(
                probe_name=self.name,
                target_id=target.get("TargetId", "unknown"),
                status=ProbeStatus.OK,
                latency_ms=round(elapsed_ms, 2),
                metrics={"latency_ms": round(elapsed_ms, 2), "banner": banner, "port": port},
            )
        except socket.timeout:
            return ProbeResult(
                probe_name=self.name,
                target_id=target.get("TargetId", "unknown"),
                status=ProbeStatus.TIMEOUT,
                error=f"SSH connection timed out after {self.timeout_ms}ms",
            )
        except OSError as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return ProbeResult(
                probe_name=self.name,
                target_id=target.get("TargetId", "unknown"),
                status=ProbeStatus.FAILED,
                latency_ms=round(elapsed_ms, 2),
                error=str(exc),
            )
