"""Check for PARLLAMA Updates on pypi"""

import requests
from bs4 import BeautifulSoup
from parllama import __version__


def get_latest_version() -> str:
    """Get project version"""
    url = "https://pypi.org/project/parllama/"
    response = requests.get(url, timeout=5)
    soup = BeautifulSoup(response.text, "html.parser")
    header = soup.find("h1", class_="package-header__name")
    if not header:
        return ""
    version = header.text.strip().split(" ")[-1]
    return version


def check_for_updates() -> None:
    """Check for updates"""
    latest_version = get_latest_version()
    if latest_version == __version__:
        print("You are using the latest version of PARLLAMA.")
    else:
        print(f"New version of PARLLAMA is available: {latest_version}")
        print("To update, run `pipx install parllama --force`.")


if __name__ == "__main__":
    check_for_updates()
