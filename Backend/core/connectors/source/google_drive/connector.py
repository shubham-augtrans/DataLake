import io
import os
import re

import pandas as pd
import requests
from django.conf import settings

from connectors.source.base import BaseConnector

DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
REQUEST_TIMEOUT = 30

# Matches both drive.google.com/drive/folders/<id> and the older
# ?id=<id> style link, with or without a trailing query string.
FOLDER_ID_PATTERN = re.compile(r"/folders/([a-zA-Z0-9_-]+)|[?&]id=([a-zA-Z0-9_-]+)")

FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

# Google-native formats (Sheets/Docs/Slides) have no raw file bytes - Drive
# must export them to a concrete format first. Anything not listed here
# (Forms, Sites, Drawings, ...) isn't supported.
GOOGLE_EXPORT_MIME_TYPES = {
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.document": "application/pdf",
    "application/vnd.google-apps.presentation": "application/pdf",
}

# Extensions this connector can parse into rows for the Iceberg table
# ingestion path (see GoogleDriveToMinioJobBuilder). Everything else in the
# folder - images, video, PDFs, zips, etc. - is copied through as a raw
# object instead of being parsed.
TABULAR_EXTENSIONS = {".csv", ".xlsx", ".xls"}


class GoogleDriveError(Exception):
    pass


def is_tabular_filename(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in TABULAR_EXTENSIONS


class GoogleDriveConnector(BaseConnector):
    """
    Connector for a public Google Drive folder ("Anyone with the link" -
    no OAuth, since this project has no per-user Google identity to
    authenticate as). A folder can hold anything - CSVs, spreadsheets,
    images, video, PDFs - so this connector offers two ways to pull a file
    out, and GoogleDriveToMinioJobBuilder picks between them per-file:

    - read_asset(): parses a tabular file (CSV/XLSX/XLS, or a Google Sheet
      exported to CSV) into a DataFrame, for the row-based Iceberg
      ingestion path.
    - download_raw(): returns the raw bytes (and content type) of ANY
      file unmodified, for landing it as an object in MinIO as-is - the
      right path for images, video, PDFs, archives, and anything else
      that isn't tabular data.

    Subfolders are not recursed into - only files directly inside the
    given folder are listed/fetched.
    """

    def __init__(self, datasource):
        self.datasource = datasource

        if not settings.GOOGLE_DRIVE_API_KEY:
            raise GoogleDriveError(
                "GOOGLE_DRIVE_API_KEY is not configured on the backend - "
                "set it in the .env file to enable Google Drive sources."
            )

        config = datasource.configuration or {}
        folder_url = config.get("folder_url", "")
        self.folder_id = self._extract_folder_id(folder_url)

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
        response = requests.get(
            f"{DRIVE_API_BASE}/files",
            params={
                "q": f"'{self.folder_id}' in parents and trashed = false",
                "key": settings.GOOGLE_DRIVE_API_KEY,
                "fields": "files(id,name,mimeType,size,modifiedTime)",
                "pageSize": 200,
            },
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            raise GoogleDriveError(
                f"Google Drive API error ({response.status_code}): {response.text[:300]}. "
                f"Make sure the folder is shared as 'Anyone with the link'."
            )

        files = response.json().get("files", [])

        # Subfolders aren't recursed into - listing/ingesting one would
        # need its own folder ID anyway, so just skip them here.
        return [f for f in files if f.get("mimeType") != FOLDER_MIME_TYPE]

    def is_tabular(self, filename):
        """
        Whether this file should go through the row-based Iceberg
        ingestion path (read_asset()) rather than the raw object copy
        path (download_raw()) - by extension, or Drive's own spreadsheet
        type for a Google Sheet with no tabular file extension.
        """
        file_meta = self._find_file(filename)
        return is_tabular_filename(filename) or file_meta.get("mimeType") == "application/vnd.google-apps.spreadsheet"

    def _find_file(self, filename):
        files = self._list_files()
        match = next((f for f in files if f["name"] == filename), None)

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
                {"Name": f["name"]}
                for f in files
            ]
        }

    def list_assets(self, bucket=None):
        """
        List files in the folder. `bucket` is accepted (and ignored) only
        to match the generic list-assets view's call signature - a Drive
        folder has no bucket concept, the folder itself is the source.
        """
        files = self._list_files()

        return [
            {
                "Key": f["name"],
                "id": f["id"],
                "mimeType": f.get("mimeType"),
                "Size": int(f["size"]) if f.get("size") else 0,
                "LastModified": f.get("modifiedTime"),
                "isTabular": is_tabular_filename(f["name"]) or f.get("mimeType") in GOOGLE_EXPORT_MIME_TYPES,
            }
            for f in files
        ]

    def _download(self, file_meta):
        """
        Raw bytes for one file - exported first if it's a Google-native
        format (no raw bytes of its own), downloaded as-is otherwise.
        Shared by read_asset() and download_raw() so there's one place
        that knows how Drive's export vs. media endpoints differ.
        """
        mime_type = file_meta.get("mimeType")

        if mime_type in GOOGLE_EXPORT_MIME_TYPES:
            url = f"{DRIVE_API_BASE}/files/{file_meta['id']}/export"
            params = {"mimeType": GOOGLE_EXPORT_MIME_TYPES[mime_type], "key": settings.GOOGLE_DRIVE_API_KEY}
            content_type = GOOGLE_EXPORT_MIME_TYPES[mime_type]

        elif mime_type and mime_type.startswith("application/vnd.google-apps."):
            raise GoogleDriveError(
                f"'{file_meta['name']}' is a Google {mime_type.rsplit('.', 1)[-1]} file, "
                f"which this connector can't export. Supported Google-native types: "
                f"Sheets, Docs, Slides."
            )

        else:
            url = f"{DRIVE_API_BASE}/files/{file_meta['id']}"
            params = {"alt": "media", "key": settings.GOOGLE_DRIVE_API_KEY}
            content_type = mime_type or "application/octet-stream"

        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)

        if response.status_code != 200:
            raise GoogleDriveError(
                f"Failed to download '{file_meta['name']}' ({response.status_code}): {response.text[:300]}"
            )

        return response.content, content_type

    def read_asset(self, filename):
        """
        Download one file by name and parse it into a DataFrame - CSV and
        Excel (.xlsx/.xls) directly, Google Sheets after being exported to
        CSV. Only call this for a file is_tabular_filename() (or Drive's
        own spreadsheet type) says is tabular.
        """
        file_meta = self._find_file(filename)
        content, content_type = self._download(file_meta)

        ext = os.path.splitext(filename)[1].lower()

        try:
            if ext in (".xlsx", ".xls"):
                return pd.read_excel(io.BytesIO(content))
            return pd.read_csv(io.BytesIO(content))
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
        return self._download(file_meta)
