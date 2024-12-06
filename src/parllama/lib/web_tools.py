"""Web tools"""

from __future__ import annotations

import os
import time
from typing import Literal

from bs4 import BeautifulSoup
from pydantic import BaseModel

from rich.console import Console
from rich.repr import rich_repr


from .user_agents import get_random_user_agent

console = Console(stderr=True)


@rich_repr
class GoogleSearchResult(BaseModel):
    """Google search result."""

    title: str
    link: str
    snippet: str


def web_search(query: str, *, num_results: int = 3, verbose: bool = False) -> list[GoogleSearchResult]:
    """Google web search."""
    from langchain_google_community import GoogleSearchAPIWrapper

    if verbose:
        console.print(f"[bold green]Web search:[bold yellow] {query}")

    search = GoogleSearchAPIWrapper(
        google_cse_id=os.environ.get("GOOGLE_CSE_ID"),
        google_api_key=os.environ.get("GOOGLE_CSE_API_KEY"),
    )
    return [GoogleSearchResult(**result) for result in search.results(query, num_results=num_results)]


def get_html_element(element, soup: BeautifulSoup) -> str:
    """
    Searches for the first occurrence of a specified HTML element in a BeautifulSoup object and returns its text.

    Parameters:
    - element (str): The tag name of the HTML element to search for (e.g., 'h1', 'div').
    - soup (BeautifulSoup): A BeautifulSoup object containing the parsed HTML document.

    Returns:
    - str: The text of the first occurrence of the specified element if found; otherwise, an empty string.
    """
    result = soup.find(element)
    if result:
        return result.text

    # print(f"No element ${element} found.")
    return ""


def fetch_url(
    urls: str | list[str],
    *,
    fetch_using: Literal["playwright", "selenium"] = "playwright",
    sleep_time: int = 1,
    verbose: bool = False,
) -> list[str]:
    """Fetch the contents of a webpage."""
    if fetch_using == "playwright":
        return fetch_url_playwright(urls, sleep_time, verbose)
    return fetch_url_selenium(urls, sleep_time, verbose)


def fetch_url_selenium(urls: str | list[str], sleep_time: int = 1, verbose: bool = False) -> list[str]:
    """Fetch the contents of a webpage."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    if isinstance(urls, str):
        urls = [urls]

    os.environ["WDM_LOG_LEVEL"] = "0"
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,1024")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])  # Disable logging
    options.add_argument("--log-level=3")  # Suppress console logging
    options.add_argument("--silent")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--ignore-certificate-errors")
    # Randomize user-agent to mimic different users
    options.add_argument("user-agent=" + get_random_user_agent())
    options.add_argument("--window-position=-2400,-2400")
    options.add_argument("--headless=new")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(10)

    results: list[str] = []
    for url in urls:
        if verbose:
            console.print(f"[bold blue]Selenium fetching content from {url}...[/bold blue]")
        try:
            driver.get(url)
            if verbose:
                console.print("[bold green]Page loaded. Scrolling and waiting for dynamic content...[/bold green]")
                console.print(f"[bold yellow]Sleeping for {sleep_time} seconds...[/bold yellow]")
            time.sleep(sleep_time)  # Sleep for the specified time
            # Scroll to the bottom of the page
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)  # Wait a bit for any dynamic content to load
            results.append(driver.page_source)
        except Exception as e:
            if verbose:
                console.print(f"[bold red]Error fetching content from {url}: {str(e)}[/bold red]")
            results.append("")
    try:
        driver.quit()
    except Exception as _:
        pass

    return results


def fetch_url_playwright(urls: str | list[str], sleep_time: int = 1, verbose: bool = False) -> list[str]:
    """
    Fetch HTML content from a URL using Playwright.

    Args:
        urls (Union[str, list[str]]): The URL(s) to fetch.
        sleep_time (int, optional): The number of seconds to sleep between requests. Defaults to 1.
        verbose (bool, optional): Whether to print verbose output. Defaults to False.

    Returns:
        list[str]: The fetched HTML content as a list of strings.
    """
    from playwright.sync_api import sync_playwright

    if isinstance(urls, str):
        urls = [urls]

    results: list[str] = []

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as e:
            console.print(
                "[bold red]Error launching playwright browser:[/bold red] Make sure you install playwright: `uv tool install playwright` then run `playwright install chromium`."
            )
            raise e
            # return ["" * len(urls)]
        context = browser.new_context(viewport={"width": 1280, "height": 1024}, user_agent=get_random_user_agent())

        page = context.new_page()
        for url in urls:
            if verbose:
                console.print(f"[bold blue]Playwright fetching content from {url}...[/bold blue]")
            try:
                page.goto(url)

                # Add delays to mimic human behavior
                if sleep_time > 0:
                    page.wait_for_timeout(sleep_time * 1000)  # Use the specified sleep time

                # Add more realistic actions like scrolling
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1000)  # Simulate time taken to scroll and read
                html = page.content()
                results.append(html)
                # if verbose:
                #     console.print(
                #         Panel(
                #             html[0:500] + "...",
                #             title="[bold green]Snippet[/bold green]",
                #         )
                #     )
            except Exception as e:
                console.log(e)
                if verbose:
                    console.print(f"[bold red]Error fetching content from {url}[/bold red]: {str(e)}")
                results.append("")
        try:
            browser.close()
        except Exception as _:
            pass

    return results


def fetch_url_and_convert_to_markdown(
    urls: str | list[str],
    *,
    fetch_using: Literal["playwright", "selenium"] = "playwright",
    sleep_time: int = 1,
    verbose: bool = False,
) -> list[str]:
    """Fetch the contents of a webpage and convert it to markdown."""
    import html2text

    if isinstance(urls, str):
        urls = [urls]
    pages = fetch_url(urls, fetch_using=fetch_using, sleep_time=sleep_time, verbose=verbose)

    if verbose:
        console.print("[bold green]Converting fetched content to markdown...[/bold green]")
    results: list[str] = []
    for html_content in pages:
        soup = BeautifulSoup(html_content, "html.parser")
        for element in soup.find_all(
            [
                "header",
                "footer",
                "script",
                "source",
                "style",
                "head",
                "img",
                "svg",
                "iframe",
            ]
        ):
            element.decompose()  # Remove these tags and their content

        html_content = soup.prettify(formatter="html")

        ### text separators
        # Find all elements with role="separator"
        separator_elements = soup.find_all(attrs={"role": "separator"})

        # replace with <hr> element, markdown recognizes this
        for element in separator_elements:
            html_content = html_content.replace(str(element), "<hr>")

        ### code blocks
        html_content = html_content.replace("<pre", "```<pre")
        html_content = html_content.replace("</pre>", "</pre>```")

        ### convert to markdown
        converter = html2text.HTML2Text()
        converter.ignore_links = True
        converter.ignore_images = True
        results.append(converter.handle(html_content))

        # results.append(md(soup))
    if verbose:
        console.print("[bold green]Conversion to markdown complete.[/bold green]")
    return results
