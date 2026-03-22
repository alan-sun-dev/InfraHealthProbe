"""Allow running as `python -m infra`."""

from .cli import main
import sys

sys.exit(main())
