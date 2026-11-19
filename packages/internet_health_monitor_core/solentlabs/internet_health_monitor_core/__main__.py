"""Allow `python -m solentlabs.internet_health_monitor_core`."""

import sys

from .cli import main

sys.exit(main())
