"""Various types, utility functions and decorators."""

from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import math
import os
import random
import re
import string
import subprocess
import sys
import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from os import listdir
from os.path import isfile, join
from re import Match, Pattern
from typing import Any

import select
from markdownify import MarkdownConverter
from bs4 import BeautifulSoup
from rich.console import Console

console = Console(stderr=True)

DECIMAL_PRECESSION = 5


def has_stdin_content():
    if os.name == "nt":  # Windows
        if sys.stdin.isatty():
            import msvcrt

            return msvcrt.kbhit()
        else:
            # Handle piped input on Windows
            return True  # Assume there's input available
    else:  # Unix-like systems
        if sys.stdin.isatty():
            rlist, _, _ = select.select([sys.stdin], [], [], 0)
            return sys.stdin in rlist
        else:
            # Handle piped input on Unix-like systems
            return True  # Assume there's input available


def md(soup: BeautifulSoup, **options) -> str:
    """
    Convert BeautifulSoup object to Markdown.

    :param soup: The BeautifulSoup object to convert.
    :param options: Additional options to pass to the converter.
    :return: The converted Markdown string.
    """
    return MarkdownConverter(**options).convert_soup(soup)


def id_generator(size: int = 6, chars: str = string.ascii_uppercase + string.digits) -> str:
    """
    Generates a random string of uppercase letters and digits.

    :param size: The length of the string to generate.
    :param chars: The characters to use for the string.
    :return: The random string.
    """
    return "".join(random.choice(chars) for _ in range(size))


def json_serial(obj: Any) -> str:
    """
    JSON serializer for objects not serializable by default json code.

    :param obj: The object to serialize.
    :return: The serialized object.
    """

    if isinstance(obj, datetime | date):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def coalesce(*arg):  # type: ignore
    """
    Return first item that is not None.

    :param arg: The items to check.
    :return: The first non-None item.
    """
    return next((a for a in arg if a is not None), None)


def chunks(lst: list, n: int) -> Generator[list, None, None]:
    """
    Yield successive n-sized chunks from lst.

    :param lst: The list to split.
    :param n: The size of the chunks.
    :return: The chunks.
    """
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def to_camel_case(snake_str: str) -> str:
    """
    Convert a snake_case string to CamelCase.

    :param snake_str: The snake_case string.
    :return: The CamelCase string.
    """
    components = snake_str.split("_")
    # We capitalize the first letter of each component except the first one
    # with the 'title' method and join them together.
    return components[0] + "".join(x.title() for x in components[1:])


def to_class_case(snake_str: str) -> str:
    """
    Convert a snake_case string to ClassCase.
    Spaces are converted to underscores before conversion.

    :param snake_str: The snake_case string.
    :return: The ClassCase string.
    """
    components = snake_str.replace(" ", "_").split("_")
    # We capitalize the first letter of each component
    # with the 'title' method and join them together.
    return "".join(x.title() for x in components[0:])


def get_files(path: str, ext: str = "") -> list[str]:
    """Return list of file names in alphabetical order inside of provided path non-recursively.
    Omitting files not ending with ext."""
    ret = [f for f in listdir(path) if isfile(join(path, f)) and (not ext or not f.endswith(ext))]
    ret.sort()
    return ret


# tests if value is able to be converted to float
def is_float(s: any) -> bool:  # type: ignore
    """Test if value is able to be converted to float."""
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


# tests if value is able to be converted to int
def is_int(s: any) -> bool:  # type: ignore
    """Test if value is able to be converted to int."""
    try:
        int(s)
        return True
    except (ValueError, TypeError):
        return False


def is_date(date_text: str, fmt: str = "%Y/%m/%d") -> bool:
    """Test if value is a valid date in format of provided format defaults to "%Y/%m/%d"."""
    try:
        datetime.strptime(date_text, fmt)
        return True
    except ValueError:
        return False


def has_value(v: Any, search: str, depth: int = 0) -> bool:
    """Recursively search data structure for search value"""
    # don't go more than 3 levels deep
    if depth > 4:
        return False
    # if is a dict, search all dict values recursively
    if isinstance(v, dict):
        for dv in v.values():
            if has_value(dv, search, depth + 1):
                return True
    # if is a list, search all list values recursively
    if isinstance(v, list):
        for li in v:
            if has_value(li, search, depth + 1):
                return True
    # if is an int, trim off .00 for search if it exists then compare
    if isinstance(v, int):
        search = search.rstrip(".00")
        if str(v) == search:
            return True
    # if is a float, truncate string version of float to same size as search
    if isinstance(v, float):
        v = str(v)[0 : len(search)]
        if search == v:
            return True
    # if is a string, strip and lowercase it then check if string starts with search
    if isinstance(v, str):
        if v.strip().lower().startswith(search) or v.strip().lower().endswith(search):
            return True
    return False


def is_zero(val: any) -> bool:  # type: ignore
    """Test if value is zero."""
    if val is None:
        return False
    t = type(val)
    if t is Decimal:
        return val.round(DECIMAL_PRECESSION).is_zero()
    if t is float:
        return math.isclose(round(val, 5), 0, rel_tol=1e-05)
    if t is int:
        return 0 == val
    return False


def non_zero(val: any) -> bool:  # type: ignore
    """Test if value is not zero."""
    return not is_zero(val)


def dict_keys_to_lower(dictionary: dict) -> dict:
    """
    Return a new dictionary with all keys lowercase
    @param dictionary: dict with keys that you want to lowercase
    @return: new dictionary with lowercase keys
    """
    return {k.lower(): v for k, v in dictionary.items()}


def is_valid_uuid_v4(value: str) -> bool:
    """Test if value is a valid UUID v4."""
    try:
        uuid_obj = uuid.UUID(value, version=4)
        return str(uuid_obj) == value  # Check if the string representation matches
    except ValueError:
        return False


def parse_csv_text(csv_data: StringIO) -> list[dict]:
    """
    Reads in a CSV file as text and returns it as a list of dictionaries.

    Args:
            csv_data (StringIO): The CSV file as text.

    Returns:
            list[dict]: The CSV data as a list of dictionaries.
    """
    return list(csv.DictReader(csv_data))


def read_text_file_to_stringio(file_path: str, encoding: str = "utf-8") -> StringIO:
    """
    Reads in a text file and returns it as a StringIO object.

    Args:
            file_path (str): The path to the file to read.
            encoding (str): The encoding of the file.

    Returns:
            StringIO: The text file as a StringIO object.
    """
    with open(file_path, encoding=encoding) as file:
        return StringIO(file.read())


def md5_hash(data: str) -> str:
    """
    Returns a md5 hash of the input data.

    Args:
            data (str): The input data.

    Returns:
            str: The md5 hash of the input data.
    """
    md5 = hashlib.md5()
    md5.update(data.encode())
    return md5.hexdigest()


def sha1_hash(data: str) -> str:
    """
    Returns a SHA1 hash of the input data.

    Args:
            data (str): The input data.

    Returns:
            str: The SHA1 hash of the input data.
    """
    sha1 = hashlib.sha1()
    sha1.update(data.encode())
    return sha1.hexdigest()


def sha256_hash(data: str) -> str:
    """
    Returns a SHA256 hash of the input data.

    Args:
            data (str): The input data.

    Returns:
            str: The SHA256 hash of the input data.
    """
    sha256 = hashlib.sha256()
    sha256.update(data.encode())
    return sha256.hexdigest()


def nested_get(dictionary: dict, keys: str | list[str]) -> Any:
    """
    Returns the value for a given key in a nested dictionary.

    Args:
            dictionary (dict): The nested dictionary to search.
            keys (str | list[str]): The key or list of keys to search for.

    Returns:
            Any: The value for the given key or None if the key does not exist.
    """
    if isinstance(keys, str):
        keys = keys.split(".")
    if keys and dictionary:
        element = keys[0]
        if element in dictionary:
            if len(keys) == 1:
                return dictionary[element]
            return nested_get(dictionary[element], keys[1:])
    return None


def override(cls):  # type: ignore
    """
    A decorator to ensure that the decorated method overrides a method in its superclass.
    """

    def overrider(method):  # type: ignore
        if method.__name__ not in dir(cls):
            raise AttributeError(f"Method {method.__name__} is not overriding any method of {cls.__name__}.")
        return method

    return overrider


@contextmanager
def add_module_path(path: str) -> Generator[None, None, None]:
    """Add a module path to sys.path temporarily."""
    sys.path.append(path)
    try:
        yield
    finally:
        try:
            sys.path.remove(path)
        except ValueError:
            # path is not in sys.path
            pass


@contextmanager
def catch_to_logger(logger: any, re_throw: bool = False) -> Generator[None, None, None]:  # type: ignore
    """Catch exceptions and log them to a logger."""
    try:
        yield
    except Exception as e:
        if logger and hasattr(logger, "exception"):
            logger.exception(e)  # type: ignore
            if re_throw:
                raise e
        else:
            raise e


@contextmanager
def timer_block(label: str = "Timer") -> Generator[None, None, None]:
    """Time a block of code."""

    start_time = time.time()
    try:
        yield
    finally:
        end_time = time.time()
        elapsed_time = end_time - start_time
        console.print(f"{label} took {elapsed_time:.4f} seconds.")


def str_ellipsis(s: str, max_len: int, pad_char: str = " ") -> str:
    """Return a left space padded string exactly max_len with ellipsis if it exceeds max_len."""
    if len(s) <= max_len:
        if pad_char:
            return s.ljust(max_len, pad_char)
        return s
    return s[: max_len - 3] + "..."


def camel_to_snake(name: str, _re_snake: Pattern[str] = re.compile("[a-z][A-Z]")) -> str:
    """Convert name from CamelCase to snake_case.
    Args:
        name: A symbol name, such as a class name.
    Returns:
        Name in camel case.
    """

    def repl(match: Match[str]) -> str:
        lower: str
        upper: str
        lower, upper = match.group()  # type: ignore
        return f"{lower}_{upper.lower()}"

    return _re_snake.sub(repl, name).lower()


def detect_syntax(text: str) -> str | None:
    """Detect the syntax of the text."""
    lines = text.split("\n")
    if len(lines) > 0:
        line = lines[0]
        if line.startswith("#!"):
            if line.endswith("/bash") or line.endswith("/sh") or line.endswith(" bash") or line.endswith(" sh"):
                return "bash"
    return None


def hash_list_by_key(data: list[dict], id_key: str = "message_id") -> dict:
    """Hash a list of dictionaries by a key."""
    return {item[id_key]: item for item in data}


def run_shell_cmd(cmd: str) -> str | None:
    """Run a command and return the output."""
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, check=True, encoding="utf-8").stdout.strip()
    except Exception as _:
        return None


def output_to_dicts(output: str) -> list[dict[str, Any]]:
    """Convert a tab-delimited output to a list of dicts."""
    if not output:
        return []
    # split string on newline loop over each line and convert
    # Use csv module to parse the tab-delimited output
    reader = csv.DictReader(io.StringIO(output), delimiter="\t")
    ret = []
    for model in reader:
        mod = {}
        for key, value in model.items():
            if not isinstance(key, str):
                continue
            mod[key.strip().lower()] = value.strip()
        ret.append(mod)
    return ret


def run_cmd(params: list[str]) -> str | None:
    """Run a command and return the output."""
    try:
        result = subprocess.run(params, capture_output=True, text=True, check=True)
        ret = result.stdout.strip()
        # Split the output into lines
        lines = [line for line in ret.splitlines() if not line.startswith("failed to get console mode")]

        # Get the last two lines
        return "\n".join(lines)
    except subprocess.CalledProcessError as e:
        console.print(f"Error running command {e.stderr}")
        return None


def read_env_file(filename: str) -> dict[str, str]:
    """
    Read environment variables from a file into a dictionary

    Args:
        filename (str): The name of the file to read

    Returns:
        Dict[str, str]: A dictionary containing the environment variables
    """
    env_vars: dict[str, str] = {}
    if not os.path.exists(filename):
        return env_vars
    with open(filename, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            try:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()
            except Exception as e:
                console.print(f"Error: {e} --- line {line}")
    return env_vars


def all_subclasses(cls) -> set[type]:
    """Return all subclasses of a given class."""
    return set(cls.__subclasses__()).union([s for c in cls.__subclasses__() for s in all_subclasses(c)])


@contextlib.contextmanager
def suppress_output():
    """Context manager to suppress stdout and stderr."""
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        try:
            sys.stdout = devnull
            sys.stderr = devnull
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
