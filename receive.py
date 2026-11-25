from concurrent.futures import (
    FIRST_COMPLETED,
    ThreadPoolExecutor,
    wait,
)
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import Request, urlopen

import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import threading
import time


# Address of the existing server on the sending machine.
BASE_URL = "http://192.168.3.249:8000/"

# Files and folders will be recreated here on the receiving machine.
DESTINATION = Path(r"C:\Users\TelvinCaesarVarfley\dev")

# Number of files downloaded at the same time.
MAX_WORKERS = 6

# Maximum number of downloads running or waiting in the queue.
MAX_PENDING_DOWNLOADS = MAX_WORKERS * 2

TIMEOUT_SECONDS = 60
MAX_RETRIES = 8
CHUNK_SIZE = 1024 * 1024

EXCLUDED_FOLDERS = {
    "node_modules",
    "google-cloud-sdk",
    ".next",
    ".nuxt",
    ".cache",
    ".parcel-cache",
    ".turbo",
    ".angular",
    "coverage",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
}

EXCLUDED_FILES = {
    ".ds_store",
    "thumbs.db",
}

EXCLUDED_FILE_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".tsbuildinfo",
    ".log",
)

# The checkpoint and partial downloads are kept here.
STATE_DIRECTORY = DESTINATION / ".transfer-state"
PARTIAL_DIRECTORY = STATE_DIRECTORY / "partials"
CHECKPOINT_FILE = STATE_DIRECTORY / "checkpoint.sqlite3"
LOG_FILE = STATE_DIRECTORY / "transfer-failures.log"

summary = {
    "downloaded": 0,
    "existing_skipped": 0,
    "excluded": 0,
    "failed": 0,
}

seen_folders = set()

print_lock = threading.Lock()
summary_lock = threading.Lock()


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")

            if href:
                self.links.append(href)


class Checkpoint:
    """
    Stores a record for each completed download.

    A lock protects the database because multiple download threads
    use it at the same time.
    """

    def __init__(self, database_path):
        self.lock = threading.Lock()
        self.connection = sqlite3.connect(
            str(database_path),
            check_same_thread=False,
        )

        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS completed_files (
                    source_url TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    local_size INTEGER NOT NULL,
                    local_mtime_ns INTEGER NOT NULL,
                    completed_at TEXT NOT NULL,
                    PRIMARY KEY (source_url, destination)
                )
                """
            )

    def record(self, url, target):
        stat = target.stat()

        with self.lock:
            with self.connection:
                self.connection.execute(
                    """
                    INSERT OR REPLACE INTO completed_files (
                        source_url,
                        destination,
                        local_size,
                        local_mtime_ns,
                        completed_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        url,
                        str(target),
                        stat.st_size,
                        stat.st_mtime_ns,
                        time.strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                )

    def close(self):
        with self.lock:
            self.connection.close()


def print_message(message):
    with print_lock:
        print(message, flush=True)


def increment_summary(name):
    with summary_lock:
        summary[name] += 1


def write_failure(message):
    with print_lock:
        STATE_DIRECTORY.mkdir(parents=True, exist_ok=True)

        with open(LOG_FILE, "a", encoding="utf-8") as output:
            output.write(
                time.strftime("%Y-%m-%d %H:%M:%S")
                + " "
                + message
                + "\n"
            )

        print("FAILED: " + message, flush=True)


def get_remote_metadata(url):
    request = Request(
        url,
        method="HEAD",
        headers={"Accept-Encoding": "identity"},
    )

    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        size_header = response.headers.get("Content-Length")
        last_modified = response.headers.get("Last-Modified")
        etag = response.headers.get("ETag")

    size = int(size_header) if size_header is not None else None

    return {
        "size": size,
        "last_modified": last_modified,
        "etag": etag,
    }


def remote_modified_timestamp(metadata):
    """Parse the server's HTTP modification date, if valid."""
    try:
        parsed = parsedate_to_datetime(metadata["last_modified"])
        return parsed.timestamp() if parsed.tzinfo is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def preserve_remote_modified_time(path, timestamp):
    if timestamp is not None:
        os.utime(path, (timestamp, timestamp))


def get_directory_links(url):
    request = Request(url, headers={"Accept": "text/html"})

    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        page = response.read().decode("utf-8", errors="replace")

    if "Directory listing for" not in page:
        raise RuntimeError(
            "Server did not return a directory listing: " + url
        )

    parser = LinkParser()
    parser.feed(page)
    return parser.links


def direct_child_name(href):
    """
    Accept only a direct child name from a directory listing.
    """
    parsed = urlsplit(href)

    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        return None

    raw_name = parsed.path.rstrip("/")

    if not raw_name or "/" in raw_name:
        return None

    name = unquote(raw_name)

    if (
        name in ("", ".", "..")
        or "/" in name
        or "\\" in name
        or ":" in name
        or "\x00" in name
    ):
        return None

    return name


def is_inside_git(relative_path):
    return any(
        part.lower() == ".git"
        for part in relative_path.parts
    )


def partial_paths(url):
    """
    Use a stable filename in the state folder so partial downloads
    don't conflict with actual project files.
    """
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()

    partial = PARTIAL_DIRECTORY / (key + ".partial")
    metadata = PARTIAL_DIRECTORY / (key + ".json")

    return partial, metadata


def read_partial_metadata(path):
    try:
        with open(path, "r", encoding="utf-8") as source:
            return json.load(source)
    except (OSError, ValueError):
        return None


def write_partial_metadata(path, metadata):
    temporary = path.with_name(path.name + ".tmp")

    with open(temporary, "w", encoding="utf-8") as output:
        json.dump(metadata, output)

    os.replace(temporary, path)


def can_resume(metadata):
    """
    Require a remote size and a version indicator before resuming.

    Last-Modified and ETag are not content hashes, but they help
    avoid resuming a partial from an older version of a file.
    """
    return (
        metadata["size"] is not None
        and (
            metadata["last_modified"] is not None
            or metadata["etag"] is not None
        )
    )


def download_file(url, target, checkpoint):
    partial, partial_metadata_file = partial_paths(url)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            PARTIAL_DIRECTORY.mkdir(parents=True, exist_ok=True)

            # Always check the sender; a local checkpoint cannot detect updates.
            metadata = get_remote_metadata(url)
            remote_size = metadata["size"]
            remote_modified = remote_modified_timestamp(metadata)

            if target.exists():
                if not target.is_file():
                    raise OSError("Destination is not a file: " + str(target))
                if remote_modified is None:
                    raise ValueError(
                        "Cannot compare files: server did not provide a valid "
                        "Last-Modified header: " + url
                    )
                # HTTP dates have one-second precision.
                if remote_modified <= math.floor(target.stat().st_mtime):
                    increment_summary("existing_skipped")
                    print_message("Skipped; local file is up to date: " + str(target))
                    return
                print_message("Source is newer; updating: " + str(target))

            saved_metadata = read_partial_metadata(
                partial_metadata_file
            )

            # Only resume a partial if its recorded source metadata
            # still matches the current source metadata.
            if (
                not can_resume(metadata)
                or saved_metadata != metadata
            ):
                partial.unlink(missing_ok=True)
                partial_metadata_file.unlink(missing_ok=True)

            write_partial_metadata(partial_metadata_file, metadata)

            offset = partial.stat().st_size if partial.exists() else 0

            if remote_size is not None and offset > remote_size:
                partial.unlink(missing_ok=True)
                offset = 0

            # Create a partial file for an empty remote file.
            if remote_size == 0 and not partial.exists():
                partial.touch()

            if (
                partial.exists()
                and remote_size is not None
                and offset == remote_size
            ):
                preserve_remote_modified_time(partial, remote_modified)
                os.replace(partial, target)
                partial_metadata_file.unlink(missing_ok=True)
                checkpoint.record(url, target)
                increment_summary("downloaded")

                print_message(
                    "Completed from partial file: " + str(target)
                )
                return

            headers = {"Accept-Encoding": "identity"}

            if offset > 0:
                headers["Range"] = "bytes={0}-".format(offset)

                # If supported, this asks the server to return the
                # whole file when its version has changed.
                validator = metadata["etag"] or metadata["last_modified"]
                if validator:
                    headers["If-Range"] = validator

                print_message(
                    "Resuming at {0} bytes: {1}".format(
                        offset,
                        target,
                    )
                )
            else:
                print_message("Downloading: " + str(target))

            request = Request(url, headers=headers)

            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                status = getattr(response, "status", 200)

                if offset > 0 and status == 206:
                    content_range = response.headers.get(
                        "Content-Range",
                        "",
                    )

                    match = re.fullmatch(
                        r"bytes (\d+)-(\d+)/(\d+|\*)",
                        content_range,
                    )

                    if (
                        not match
                        or int(match.group(1)) != offset
                        or (
                            remote_size is not None
                            and match.group(3) != str(remote_size)
                        )
                    ):
                        raise IOError(
                            "Unexpected Content-Range: "
                            + content_range
                        )

                    mode = "ab"

                elif status == 200:
                    if offset > 0:
                        print_message(
                            "Server cannot resume this file; "
                            "restarting: " + str(target)
                        )

                    offset = 0
                    mode = "wb"

                else:
                    raise IOError(
                        "Unexpected HTTP status: " + str(status)
                    )

                with open(partial, mode) as output:
                    while True:
                        chunk = response.read(CHUNK_SIZE)

                        if not chunk:
                            break

                        output.write(chunk)

            actual_size = partial.stat().st_size

            if remote_size is not None and actual_size != remote_size:
                raise IOError(
                    "Incomplete file. Expected {0} bytes, got {1}."
                    .format(remote_size, actual_size)
                )

            preserve_remote_modified_time(partial, remote_modified)
            os.replace(partial, target)
            partial_metadata_file.unlink(missing_ok=True)

            # Record only after the destination file is in place.
            checkpoint.record(url, target)
            increment_summary("downloaded")

            print_message(
                "Completed: {0} ({1:.1f} MB)".format(
                    target,
                    actual_size / 1024 / 1024,
                )
            )
            return

        except Exception as error:
            if isinstance(error, ValueError) or attempt == MAX_RETRIES:
                increment_summary("failed")
                write_failure(str(target) + " | " + repr(error))
                return

            delay = min(60, 2 ** attempt)

            print_message(
                "Retry {0}/{1} for {2} in {3} seconds: {4}".format(
                    attempt,
                    MAX_RETRIES,
                    target.name,
                    delay,
                    error,
                )
            )

            time.sleep(delay)


def wait_for_downloads(pending, wait_for_all=False):
    if not pending:
        return set()

    if wait_for_all:
        done, remaining = wait(pending)
    else:
        done, remaining = wait(
            pending,
            return_when=FIRST_COMPLETED,
        )

    for future in done:
        try:
            future.result()
        except Exception as error:
            increment_summary("failed")
            write_failure(
                "Unexpected download error | " + repr(error)
            )

    return remaining


def download_folder(url, folder, executor, pending, checkpoint):
    if url in seen_folders:
        return pending

    seen_folders.add(url)

    try:
        folder.mkdir(parents=True, exist_ok=True)
        links = get_directory_links(url)
    except Exception as error:
        increment_summary("failed")
        write_failure(url + " | " + repr(error))
        return pending

    print_message("Scanning: " + url)

    for href in links:
        name = direct_child_name(href)

        if name is None:
            continue

        is_folder = urlsplit(href).path.endswith("/")
        lower_name = name.lower()
        target = folder / name
        relative_path = target.relative_to(DESTINATION)

        # Preserve all Git internals, including .git/logs.
        if not is_inside_git(relative_path):
            if is_folder and lower_name in EXCLUDED_FOLDERS:
                increment_summary("excluded")
                print_message("Excluded folder: " + str(target))
                continue

            if not is_folder and (
                lower_name in EXCLUDED_FILES
                or lower_name.endswith(EXCLUDED_FILE_SUFFIXES)
            ):
                increment_summary("excluded")
                continue

        item_url = urljoin(url, href)

        if is_folder:
            pending = download_folder(
                item_url,
                target,
                executor,
                pending,
                checkpoint,
            )
        else:
            pending.add(
                executor.submit(
                    download_file,
                    item_url,
                    target,
                    checkpoint,
                )
            )

            if len(pending) >= MAX_PENDING_DOWNLOADS:
                pending = wait_for_downloads(pending)

    return pending


def main():
    if not BASE_URL.endswith("/"):
        raise ValueError("BASE_URL must end with /.")

    if MAX_WORKERS < 1:
        raise ValueError("MAX_WORKERS must be at least 1.")

    DESTINATION.mkdir(parents=True, exist_ok=True)
    PARTIAL_DIRECTORY.mkdir(parents=True, exist_ok=True)

    checkpoint = Checkpoint(CHECKPOINT_FILE)

    print_message("Source: " + BASE_URL)
    print_message("Destination: " + str(DESTINATION))
    print_message("Parallel downloads: " + str(MAX_WORKERS))
    print_message("Checkpoint: " + str(CHECKPOINT_FILE))

    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            pending = download_folder(
                BASE_URL,
                DESTINATION,
                executor,
                set(),
                checkpoint,
            )

            wait_for_downloads(pending, wait_for_all=True)

    finally:
        checkpoint.close()

    print("\nTransfer summary")
    print("Downloaded: " + str(summary["downloaded"]))
    print(
        "Skipped existing files by date: "
        + str(summary["existing_skipped"])
    )
    print("Excluded: " + str(summary["excluded"]))
    print("Failed: " + str(summary["failed"]))
    print("Destination: " + str(DESTINATION))

    if summary["failed"] > 0:
        print("Review: " + str(LOG_FILE))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
