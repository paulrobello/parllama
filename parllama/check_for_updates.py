"""Check for PARLLAMA Updates on pypi"""

from datetime import datetime, timezone

import httpx
import requests
from bs4 import BeautifulSoup
from semver import Version

from parllama import __version__
from parllama.models.settings_data import settings
from parllama.par_event_system import ParEventSystemBase


class UpdateManager(ParEventSystemBase):
    """Update manager class"""

    url: str

    def __init__(self) -> None:
        """Initialize the update manager"""
        super().__init__(id="update_manager")
        self.url = "https://pypi.org/project/parllama/"

    async def get_latest_version(self) -> Version:
        """Get project version"""
        self.log_it("Checking for updates...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.url, timeout=5)
            soup = BeautifulSoup(response.text, "html.parser")
            header = soup.find("h1", class_="package-header__name")
            if not header:
                raise ValueError("Could not locate header")
            version = header.text.strip().split(" ")[-1]
            return Version.parse(version)
        except requests.exceptions.RequestException as e:
            raise ValueError("Could not fetch version info") from e

    async def check_for_updates(self, force: bool = False) -> None:
        """Check for updates"""
        self.log_it(f"App version is: {__version__}")
        if not force:
            last_version_check = settings.last_version_check
            if last_version_check:
                if (datetime.now(timezone.utc) - last_version_check).days < 1:
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
            settings.last_version_check = datetime.now(timezone.utc)
            settings.save()
        except (ValueError, TypeError) as e:
            if self.app:
                self.log_it(e, notify=True, severity="error")
            else:
                print(e)


update_manager = UpdateManager()
