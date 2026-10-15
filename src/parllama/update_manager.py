"""Check for PARLLAMA Updates on pypi"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx
from semver import Version

from parllama import __version__
from parllama.message_sink import MessageSink
from parllama.settings_manager import settings

logger = logging.getLogger(__name__)


class UpdateManager(MessageSink):
    """Update manager class"""

    url: str

    def __init__(self) -> None:
        """Initialize the update manager"""
        super().__init__(id="update_manager")
        self.url = "https://pypi.org/pypi/parllama/json"

    async def get_latest_version(self) -> Version:
        """Get the latest published version from PyPI.

        Raises:
            ValueError: If the request fails, PyPI returns an error status, or the
                response does not contain a parseable version.
        """
        self.log_it("Checking for updates...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.url, follow_redirects=True, timeout=settings.http.update_check_timeout)
                response.raise_for_status()
                data = response.json()
            return Version.parse(data["info"]["version"])
        except (httpx.HTTPError, KeyError, TypeError) as e:
            raise ValueError("Could not fetch version info") from e

    async def check_for_updates(self, force: bool = False) -> None:
        """Check for updates"""
        self.log_it(f"App version is: {__version__}")
        if not force:
            last_version_check = settings.last_version_check
            if last_version_check:
                if (datetime.now(UTC) - last_version_check).days < 1:
                    return
        try:
            latest_version = await self.get_latest_version()
            self.log_it(f"Latest version is: {latest_version}")

            if Version.parse(__version__) < latest_version:
                if self.app:
                    self.log_it(
                        f"New version available: {latest_version}",
                        notify=True,
                        timeout=int(settings.ui.notification_timeout_extended),
                    )
                else:
                    logger.info("New version available: %s", latest_version)
            settings.last_version_check = datetime.now(UTC)
            settings.save()
        except (ValueError, TypeError) as e:
            if self.app:
                self.log_it(e, notify=True, severity="error")
            else:
                logger.error("Failed to check for updates: %s", e)


update_manager: UpdateManager = UpdateManager()
"""Process-wide singleton. Construction performs no I/O; wiring happens in ``set_app``."""
