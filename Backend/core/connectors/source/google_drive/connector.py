import io
import os
import re

import gdown
import pandas as pd

from connectors.source.base import BaseConnector

# Matches both drive.google.com/drive/folders/<id> and the older
# ?id=<id> style link, with or without a trailing query string.
FOLDER_ID_PATTERN = re.compile(r"/folders/([a-zA-Z0-9_-]+)|[?&]id=([a-zA-Z0-9_-]+)")

# Extensions this connector can parse into rows for the Iceberg table
# ingestion path (see GoogleDriveToMinioJobBuilder). Everything else in the
# folder - images, video, PDFs, zips, etc. - is copied through as a raw
# object instead of being parsed. A file with NO extension is also treated
# as tabular: that's how a native Google Sheet/Doc/Slide shows up in a
# folder listing (no raw bytes of their own), and gdown auto-exports those
# to .xlsx/.docx/.pptx on download - read_asset() then parses whatever
# came back.
TABULAR_EXTENSIONS = {".csv", ".xlsx", ".xls"}


class GoogleDriveError(Exception):
    pass


def is_tabular_filename(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in TABULAR_EXTENSIONS or ext == ""


class GoogleDriveConnector(BaseConnector):
    """
    Connector for a public Google Drive folder ("Anyone with the link" -
    no OAuth, and no Google Cloud API key either: this scrapes the
    folder's public HTML listing via gdown (https://github.com/wkentaro/gdown),
    the same approach tools like `gdown --folder` use, rather than the
    Drive REST API - which Google requires a registered API key/OAuth
    identity for even on fully public content. A folder can hold
    anything, so this connector offers two ways to pull a file out, and
    GoogleDriveToMinioJobBuilder picks between them per-file:

    - read_asset(): parses a tabular file (CSV/XLSX/XLS, or a Google
      Sheet - gdown auto-exports those to .xlsx) into a DataFrame, for
      the row-based Iceberg ingestion path.
    - download_raw(): returns the raw bytes of ANY file unmodified, for
      landing it as an object in MinIO as-is - the right path for
      images, video, PDFs, archives, and anything else that isn't
      tabular data.

    Subfolders are not recursed into - only files directly inside the
    given folder are listed/fetched.
    """

    def __init__(self, datasource):
        self.datasource = datasource

        config = datasource.configuration or {}
        self.folder_url = config.get("folder_url", "")
        self.folder_id = self._extract_folder_id(self.folder_url)

    @staticmethod
    def _extract_folder_id(folder_url):
        if not folder_url:
            raise GoogleDriveError("This data source has no Google Drive folder URL configured.")

        match = FOLDER_ID_PATTERN.search(folder_url)

        if not match:
            raise GoogleDriveError(
                "Could not find a folder ID in that URL. Expected something like "
                "https://drive.google.com/drive/folders/<FOLDER_ID>"
            )

        return match.group(1) or match.group(2)

    def _list_files(self):
        try:
            entries = gdown.download_folder(
                url=self.folder_url,
                skip_download=True,
                quiet=True,
                use_cookies=False,
            )
        except Exception as ex:
            raise GoogleDriveError(
                f"Could not read this Drive folder: {str(ex)} "
                f"Make sure it's shared as 'Anyone with the link'."
            )

        if entries is None:
            raise GoogleDriveError(
                "Could not read this Drive folder - it may not be shared as "
                "'Anyone with the link', or the folder link is invalid."
            )

        # entries carry `path` relative to the folder, e.g. "orders.csv" for
        # a top-level file or "subdir/orders.csv" for a nested one - only
        # keep top-level files, subfolders aren't recursed into.
        return [e for e in entries if "/" not in e.path]

    def _find_file(self, filename):
        match = next((f for f in self._list_files() if f.path == filename), None)

        if match is None:
            raise GoogleDriveError(f"File '{filename}' was not found in this Drive folder.")

        return match

    def check_connection(self):
        """
        Test that the folder is reachable and public. Shaped like
        KafkaConnector.check_connection() ({"Buckets": [...]}) so the
        generic check-connection view/UI works unmodified - each "bucket"
        here is one file in the folder.
        """
        files = self._list_files()

        return {
            "Buckets": [
                {"Name": f.path}
                for f in files
            ]
        }

    def list_assets(self, bucket=None):
        """
        List files in the folder. `bucket` is accepted (and ignored) only
        to match the generic list-assets view's call signature - a Drive
        folder has no bucket concept, the folder itself is the source.
        Size/last-modified aren't available from the folder listing
        without an extra per-file request, so they're left blank.
        """
        files = self._list_files()

        return [
            {
                "Key": f.path,
                "id": f.id,
                "Size": 0,
                "LastModified": None,
                "isTabular": is_tabular_filename(f.path),
            }
            for f in files
        ]

    def _download(self, file_id, filename):
        buffer = io.BytesIO()

        try:
            gdown.download(id=file_id, output=buffer, quiet=True, use_cookies=False)
        except Exception as ex:
            raise GoogleDriveError(f"Failed to download '{filename}': {str(ex)}")

        return buffer.getvalue()

    def read_asset(self, filename):
        """
        Download one file by name and parse it into a DataFrame - CSV and
        Excel (.xlsx/.xls) directly. A file with no extension is assumed
        to be a native Google Sheet/Doc, which gdown auto-exports to
        .xlsx/.docx on download - only the Sheet case actually parses.
        Only call this for a file is_tabular_filename() says is tabular.
        """
        file_meta = self._find_file(filename)
        content = self._download(file_meta.id, filename)

        ext = os.path.splitext(filename)[1].lower()

        try:
            if ext == ".csv":
                return pd.read_csv(io.BytesIO(content))
            return pd.read_excel(io.BytesIO(content))
        except Exception as ex:
            raise GoogleDriveError(
                f"'{filename}' could not be parsed as tabular data: {str(ex)}. "
                f"Supported formats: CSV, XLSX, XLS, Google Sheets."
            )

    def download_raw(self, filename):
        """
        Download one file by name unmodified - for anything that isn't
        tabular data (images, video, PDFs, archives, ...). Returns
        (content_bytes, content_type).
        """
        file_meta = self._find_file(filename)
        content = self._download(file_meta.id, filename)

        ext = os.path.splitext(filename)[1].lower()
        content_type = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
            ".zip": "application/zip",
        }.get(ext, "application/octet-stream")

        return content, content_type
