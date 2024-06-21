"""Various utility functions and decorators."""

import csv
import hashlib
import io
import math
import os
import random
import string
import subprocess
import sys
import time
import uuid
from argparse import ArgumentParser, Namespace
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from os import listdir
from os.path import isfile, join
from typing import Any, Dict, Generator, List, Union

from textual.widgets import Button, Input
from textual.widgets._button import ButtonVariant

from parllama import __application_title__, __version__
from parllama.icons import PENCIL_EMOJI, TRASH_EMOJI

DECIMAL_PRECESSION = 5


def id_generator(
    size: int = 6, chars: str = string.ascii_uppercase + string.digits
) -> str:
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

    if isinstance(obj, (datetime, date)):
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
    ret = [
        f
        for f in listdir(path)
        if isfile(join(path, f)) and (not ext or not f.endswith(ext))
    ]
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


# pylint: disable=too-many-return-statements, too-many-branches
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
    with open(file_path, "r", encoding=encoding) as file:
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
            raise AttributeError(
                f"Method {method.__name__} is not overriding any method of {cls.__name__}."
            )
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
def catch_to_logger(logger: any, re_throw: bool = False):  # type: ignore
    """Catch exceptions and log them to a logger."""
    try:
        yield
    # pylint: disable=broad-except
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
        print(f"{label} took {elapsed_time:.4f} seconds.")


def str_ellipsis(s: str, max_len: int) -> str:
    """Return a left space padded string exactly max_len with ellipsis if it exceeds max_len."""
    if len(s) <= max_len:
        return s.ljust(max_len)
    return s[: max_len - 3] + "..."


def detect_syntax(text: str) -> str | None:
    """Detect the syntax of the text."""
    lines = text.split("\n")
    if len(lines) > 0:
        line = lines[0]
        if line.startswith("#!"):
            if (
                line.endswith("/bash")
                or line.endswith("/sh")
                or line.endswith(" bash")
                or line.endswith(" sh")
            ):
                return "bash"
    return None


def mk_field_button(
    *,
    id: str,  # pylint: disable=redefined-builtin
    classes: str = "",
    emoji: str,
    tooltip: str = "",
    variant: ButtonVariant = "default",
) -> Button:
    """Make a field button."""
    btn = Button(emoji, id=id, classes=f"field-button {classes}", variant=variant)
    if tooltip:
        btn.tooltip = tooltip
    return btn


def mk_trash_button(
    *,
    id: str = "delete",  # pylint: disable=redefined-builtin
    classes: str = "",
    tooltip: str = "Delete",
) -> Button:
    """Make a trash button."""
    return mk_field_button(
        id=id,
        classes=classes,
        emoji=TRASH_EMOJI,
        tooltip=tooltip,
        variant="error",
    )


def mk_edit_button(
    *,
    id: str = "edit",  # pylint: disable=redefined-builtin
    classes: str = "",
    tooltip: str = "Edit",
) -> Button:
    """Make a edit button."""
    return mk_field_button(
        id=id,
        classes=classes,
        emoji=PENCIL_EMOJI,
        tooltip=tooltip,
    )


def hash_list_by_key(data: list[dict], id_key: str = "id") -> dict:
    """Hash a list of dictionaries by a key."""
    return {item[id_key]: item for item in data}


def run_shell_cmd(cmd: str) -> str | None:
    """Run a command and return the output."""
    try:
        return subprocess.run(
            cmd, shell=True, capture_output=True, check=True, encoding="utf-8"
        ).stdout.strip()
    except:  # pylint: disable=bare-except
        return None


def clamp_input_value(
    input_widget: Input, min_value: int | None = None, max_value: int | None = None
) -> int:
    """Clamp the value of an input widget."""
    val: int = int(input_widget.value or 0)
    if min_value is not None and val < min_value:
        input_widget.value = str(min_value)
        return min_value
    if max_value is not None and val > max_value:
        input_widget.value = str(max_value)
        return max_value
    return val


eff_word_list_cache: list[str] = []


def get_args() -> Namespace:
    """Parse and return the command line arguments.

    Returns:
            The result of parsing the arguments.
    """

    # Create the parser object.
    parser = ArgumentParser(
        prog=__application_title__,
        description=f"{__application_title__} -- Ollama TUI.",
        epilog=f"v{__version__}",
    )

    # Add --version
    parser.add_argument(
        "-v",
        "--version",
        help="Show version information.",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    parser.add_argument(
        "-d",
        "--data-dir",
        help="Data Directory. Defaults to ~/.parllama",
    )
    parser.add_argument("-t", "--theme-name", help="Theme name. Defaults to par")
    parser.add_argument(
        "-m",
        "--theme-mode",
        help="Dark / Light mode. Defaults to dark",
        choices=["dark", "light"],
    )

    parser.add_argument(
        "--restore-defaults",
        help="Restore default settings and theme",
        default=False,
        action="store_true",
    )

    parser.add_argument(
        "--clear-cache",
        help="Clear cached data",
        default=False,
        action="store_true",
    )

    parser.add_argument(
        "--no-save",
        help="Prevent saving settings for this session.",
        default=False,
        action="store_true",
    )

    # Finally, parse the command line.
    return parser.parse_args()


def output_to_dicts(output: str) -> List[dict[str, Any]]:
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
            mod[key.strip().lower()] = value.strip()
        ret.append(mod)
    return ret


def run_cmd(params: list[str]) -> Union[str, None]:
    """Run a command and return the output."""
    try:
        result = subprocess.run(
            params, capture_output=True, text=True, check=True, universal_newlines=True
        )
        ret = result.stdout.strip()
        # Split the output into lines
        lines = [
            line
            for line in ret.splitlines()
            if not line.startswith("failed to get console mode")
        ]

        # Get the last two lines
        return "\n".join(lines)
    except subprocess.CalledProcessError as e:
        print(f"Error running command {e.stderr}")
        return None


def read_env_file(filename: str) -> Dict[str, str]:
    """
    Read environment variables from a file into a dictionary

    Args:
        filename (str): The name of the file to read

    Returns:
        Dict[str, str]: A dictionary containing the environment variables
    """
    env_vars: Dict[str, str] = {}
    if not os.path.exists(filename):
        return env_vars
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or not "=" in line:
                continue
            try:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"Error: {e} --- line {line}")
    return env_vars
