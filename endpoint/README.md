# Windows Endpoint Probe

Windows endpoint WiFi/meeting diagnostics is handled by the standalone
[Collect-WiFiMeetingTest](https://github.com/alan-sun-dev/Collect-WiFiMeetingTest) project.

InfraHealthProbe consumes its output (JSONL/CSV) via the `wifi_adapter.py` module.
It does NOT import or dot-source any PowerShell internals.

## Integration

The platform triggers WiFi collection on Windows endpoints via:
- SSH / WinRM remote command
- Windows Task Scheduler
- Manual execution by field engineer

Then fetches the output files (JSONL/CSV) via SMB, SCP, or shared directory.
