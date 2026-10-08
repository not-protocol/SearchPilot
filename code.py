#!/usr/bin/env python3
"""
Automated multi-tab Google searches in Brave (Python + Selenium).

How it works
------------
1. Asks you for a search term (for example "GPT-3").
2. Loads a list of extra keywords ("commands") from commands.txt, or uses the
   built-in DEFAULT_COMMANDS if that file doesn't exist.
3. Starts Brave through Selenium / ChromeDriver (Brave is Chromium-based).
4. For each command it opens a new tab, goes to Google, types
   "<search term> <command>" one character at a time (so you can watch it),
   and presses Enter.
5. When every search is done it waits for you to press Enter, then closes Brave.

Run it with:  python code.py
"""

import logging
import os
import platform
import shutil
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ------------------------------ Configuration ------------------------------

# Full path to the Brave executable. Leave as None to auto-detect it.
BRAVE_PATH = None

# Full path to a ChromeDriver whose major version matches Brave's Chromium
# version. Leave as None to use a "chromedriver" file sitting next to this
# script, or else whatever Selenium finds on your PATH.
CHROMEDRIVER_PATH = None

# Optional text file next to this script with one command per line.
# Blank lines and lines starting with "#" are ignored.
COMMANDS_FILE = "commands.txt"

# Used when COMMANDS_FILE is missing or empty.
DEFAULT_COMMANDS = [
    "+(mkv|mp4|avi|mov|mpg|wmv|divx|mpeg) -inurl:(jsp|pl|php|html|aspx|htm|cf|shtml) intitle:index.of -inurl:(listen77|mp3raid|mp3toss|mp3drug|index_of|index-of|wallywashis|downloadmana)",
    "+(MOBI|CBZ|CBR|CBC|CHM|EPUB|FB2|LIT|LRF|ODT|PDF|PRC|PDB|PML|RB|RTF|TCR|DOC|DOCX) -inurl:(jsp|pl|php|html|aspx|htm|cf|shtml) intitle:index.of -inurl:(listen77|mp3raid|mp3toss|mp3drug|index_of|index-of|wallywashis|downloadmana)",
    "+(mp3|wav|ac3|ogg|flac|wma|m4a|aac|mod) -inurl:(jsp|pl|php|html|aspx|htm|cf|shtml) intitle:index.of -inurl:(listen77|mp3raid|mp3toss|mp3drug|index_of|index-of|wallywashis|downloadmana)",
    "+(exe|iso|dmg|tar|7z|bz2|gz|rar|zip|apk) -inurl:(jsp|pl|php|html|aspx|htm|cf|shtml) intitle:index.of -inurl:(listen77|mp3raid|mp3toss|mp3drug|index_of|index-of|wallywashis|downloadmana)",
    "+(jpg|png|bmp|gif|tif|tiff|psd) -inurl:(jsp|pl|php|html|aspx|htm|cf|shtml) intitle:index.of -inurl:(listen77|mp3raid|mp3toss|mp3drug|index_of|index-of|wallywashis|downloadmana)",
    "-inurl:(jsp|pl|php|html|aspx|htm|cf|shtml) intitle:index.of -inurl:(listen77|mp3raid|mp3toss|mp3drug|index_of|index-of|wallywashis|downloadmana)",
    "API examples",
    "security",
]

GOOGLE_URL = "https://www.google.com"

# Delays, in seconds.
PAGE_DELAY = 1.0       # pause after Google loads, before typing starts
TYPE_DELAY = 0.08      # pause between keystrokes (0 = type instantly)
SEARCH_DELAY = 3.0     # pause on the results page before the next tab opens
ELEMENT_TIMEOUT = 20   # longest wait for Google's search box to appear

# Usual Brave locations per operating system; the first one that exists wins.
BRAVE_CANDIDATES = {
    "Windows": [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(
            r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"
        ),
    ],
    "Darwin": [  # macOS
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ],
    "Linux": [
        "/usr/bin/brave-browser",
        "/usr/bin/brave",
        "/snap/bin/brave",
        "/opt/brave.com/brave/brave-browser",
    ],
}

# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent


def find_brave():
    """Return the path to Brave's executable, or None if it can't be found."""
    if BRAVE_PATH:
        return BRAVE_PATH if os.path.isfile(BRAVE_PATH) else None

    for candidate in BRAVE_CANDIDATES.get(platform.system(), []):
        if os.path.isfile(candidate):
            return candidate

    # Last resort: look for it on PATH.
    return shutil.which("brave-browser") or shutil.which("brave")


def find_driver_path():
    """Return an explicit ChromeDriver path (configured, or next to this script)."""
    if CHROMEDRIVER_PATH:
        return CHROMEDRIVER_PATH

    name = "chromedriver.exe" if platform.system() == "Windows" else "chromedriver"
    local = SCRIPT_DIR / name
    return str(local) if local.is_file() else None


def load_commands():
    """Read commands from COMMANDS_FILE, falling back to DEFAULT_COMMANDS."""
    path = SCRIPT_DIR / COMMANDS_FILE
    if path.is_file():
        with open(path, encoding="utf-8-sig") as f:
            commands = [
                line.strip()
                for line in f
                if line.strip() and not line.lstrip().startswith("#")
            ]
        if commands:
            logging.info("Loaded %d commands from %s", len(commands), path.name)
            return commands
        logging.warning("%s has no commands in it; using the defaults", path.name)

    logging.info("Using the default list of %d commands", len(DEFAULT_COMMANDS))
    return list(DEFAULT_COMMANDS)


def type_slowly(element, text, delay):
    """Send text to an element one character at a time so the typing is visible."""
    for char in text:
        element.send_keys(char)
        if delay:
            time.sleep(delay)


def run_search(driver, query):
    """Open Google in the current tab, type `query` and press Enter.

    Returns True once the query is submitted, or False if Google's search box
    never appeared (for example because a cookie-consent or CAPTCHA page is
    showing and nobody dealt with it in time).
    """
    driver.get(GOOGLE_URL)
    time.sleep(PAGE_DELAY)

    try:
        box = WebDriverWait(driver, ELEMENT_TIMEOUT).until(
            EC.element_to_be_clickable((By.NAME, "q"))  # Google's search box
        )
    except TimeoutException:
        return False

    box.clear()
    type_slowly(box, query, TYPE_DELAY)
    box.send_keys(Keys.RETURN)
    return True


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    term = input("What do you want to search? ").strip()
    if not term:
        logging.error("No search term provided. Exiting.")
        return 1
    logging.info("Search term: %s", term)

    commands = load_commands()

    brave = find_brave()
    if not brave:
        logging.error(
            "Could not find the Brave executable. Install Brave or set "
            "BRAVE_PATH at the top of this script."
        )
        return 1
    logging.info("Using Brave at: %s", brave)

    options = webdriver.ChromeOptions()
    options.binary_location = brave  # launch Brave instead of Chrome

    driver_path = find_driver_path()
    service = Service(executable_path=driver_path) if driver_path else Service()

    try:
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as exc:
        logging.error("Could not start Brave through ChromeDriver: %s", exc)
        logging.error(
            "Check that ChromeDriver's major version matches the Chromium "
            "version shown at brave://version."
        )
        return 1

    try:
        total = len(commands)
        for i, command in enumerate(commands, start=1):
            query = f"{term} {command}"
            logging.info("[%d/%d] Searching for: %s", i, total, query)

            if i > 1:
                driver.switch_to.new_window("tab")  # opens a tab and switches to it

            if not run_search(driver, query):
                logging.warning(
                    "Search box not found after %ss (cookie-consent or CAPTCHA "
                    "page?). Skipping this command.",
                    ELEMENT_TIMEOUT,
                )
                continue

            time.sleep(SEARCH_DELAY)  # let the results sit on screen for a moment

        logging.info("All searches completed.")
        try:
            input("Press Enter to close Brave... ")
        except EOFError:
            pass
        return 0
    except WebDriverException as exc:
        logging.error("Browser error: %s", exc)
        return 1
    finally:
        try:
            driver.quit()
        except Exception:
            pass  # the browser may already be closed


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logging.info("Interrupted - closing Brave.")
        sys.exit(130)
