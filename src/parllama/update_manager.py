"""Check for PARLLAMA Updates on pypi"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import requests
from semver import Version

from parllama import __version__
from parllama.par_event_system import ParEventSystemBase
from parllama.settings_manager import settings


class UpdateManager(ParEventSystemBase):
    """Update manager class"""

    url: str

    def __init__(self) -> None:
        """Initialize the update manager"""
        super().__init__(id="update_manager")
        self.url = "https://pypi.org/pypi/parllama/json"

    async def get_latest_version(self) -> Version:
        """Get project version"""
        self.log_it("Checking for updates...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.url, follow_redirects=True, timeout=5)
                data = response.json()
            return Version.parse(data["info"]["version"])
        except requests.exceptions.RequestException as e:
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
                        timeout=8,
                    )
                else:
                    print(f"New version available: {latest_version}")
            settings.last_version_check = datetime.now(UTC)
            settings.save()
        except (ValueError, TypeError) as e:
            if self.app:
                self.log_it(e, notify=True, severity="error")
            else:
                print(e)


update_manager = UpdateManager()
