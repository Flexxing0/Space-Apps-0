"""Descubrimiento GLDAS 2.1 y diagnóstico Earthdata; nunca usa el servidor retirado."""

import os
import re
from html.parser import HTMLParser
from urllib.parse import quote, urlparse
from xml.etree import ElementTree

import requests

from services.api_service import ServiceError
from services.providers.cache import utc_now, write_json_atomic


PRODUCT = "GLDAS_NOAH025_M"
VERSION = "2.1"
VARIABLES = {
    "SoilMoi0_10cm_inst": {"unit": "kg m-2", "depth_cm": [0, 10]},
    "SoilMoi10_40cm_inst": {"unit": "kg m-2", "depth_cm": [10, 40]},
    "SoilMoi40_100cm_inst": {"unit": "kg m-2", "depth_cm": [40, 100]},
    "SoilMoi100_200cm_inst": {"unit": "kg m-2", "depth_cm": [100, 200]},
    "Evap_tavg": {"unit": "kg m-2 s-1"},
}
CMR = "https://cmr.earthdata.nasa.gov/search"


def environment_token():
    token = os.environ.get("EARTHDATA_TOKEN")
    if token and not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", token):
        invalid_codes = sorted({ord(char) for char in token if not re.fullmatch(r"[A-Za-z0-9._~+/=-]", char)})
        raise ServiceError("invalid_request", "EARTHDATA_TOKEN tiene un formato no permitido para Bearer HTTP; configurarlo sin espacios, comillas ni prefijo Bearer.",
                           details={"credential_format_valid": False,
                                    "has_whitespace": any(char.isspace() for char in token),
                                    "has_control_characters": any(ord(char) < 32 or ord(char) == 127 for char in token),
                                    "has_quotes": '"' in token or "'" in token,
                                    "has_bearer_prefix": token.lstrip().lower().startswith("bearer "),
                                    "has_paste_markers": "\x1b[200~" in token or "\x1b[201~" in token,
                                    "has_non_ascii": not token.isascii(),
                                    "invalid_character_codes": [f"U+{code:04X}" for code in invalid_codes[:16]]})
    return token


class PublicErrorText(HTMLParser):
    """Sólo texto visible de errores; excluye formularios, scripts y atributos."""
    def __init__(self):
        super().__init__()
        self.blocked = 0
        self.allowed = 0
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "form"}:
            self.blocked += 1
        if tag in {"title", "h1", "h2", "p", "pre"}:
            self.allowed += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "form"}:
            self.blocked = max(0, self.blocked - 1)
        if tag in {"title", "h1", "h2", "p", "pre"}:
            self.allowed = max(0, self.allowed - 1)

    def handle_data(self, data):
        if self.allowed and not self.blocked and data.strip():
            self.text.append(data.strip())


def public_diagnostic(response, token=None):
    """Detalle remoto acotado, sin cabeceras, cookies ni credenciales."""
    message = response.text[:12000]
    if re.search(r"(?i)<(?:!doctype|html|form)\b", message):
        parser = PublicErrorText()
        parser.feed(message)
        message = " | ".join(parser.text) or "HTML response; login/session content omitted"
    if token:
        for secret in (token, quote(token, safe="")):
            message = message.replace(secret, "[REDACTED]")
    message = re.sub(r"(?i)Bearer\s+[^\s<>\"']+", "Bearer [REDACTED]", message)
    message = re.sub(r"[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}", "[REDACTED_JWT]", message)
    return message.strip()[:1800]


def valid_descriptor(text, suffix):
    if suffix == ".dds":
        return text.lstrip().startswith("Dataset")
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return False
    return root.tag == "{http://xml.opendap.org/ns/DAP/4.0#}Dataset"


class GldasProvider:
    def __init__(self, store):
        self.store = store
        self._points = None

    def probe(self):
        token = environment_token()
        response = requests.get(CMR + "/collections.json", params={"short_name": PRODUCT, "version": VERSION}, timeout=40)
        response.raise_for_status()
        collections = response.json()["feed"]["entry"]
        collection = next((row for row in collections if row["short_name"] == PRODUCT and row["version_id"] == VERSION), None)
        if collection is None:
            raise ValueError("No se encontró el producto y versión GLDAS solicitado")
        response = requests.get(CMR + "/granules.json", params={"collection_concept_id": collection["id"],
                                "temporal": "2000-01-01T00:00:00Z,2000-01-31T23:59:59Z", "page_size": 1}, timeout=40)
        response.raise_for_status()
        granules = response.json()["feed"]["entry"]
        if not granules:
            raise ValueError("CMR no devolvió un gránulo GLDAS")
        links = [row["href"] for row in granules[0].get("links", [])
                 if urlparse(row.get("href", "")).hostname == "opendap.earthdata.nasa.gov"]
        if not links:
            raise ValueError("CMR no ofrece un enlace oficial OPeNDAP Cloud")
        headers = {"Authorization": "Bearer " + token} if token else {}
        attempts = []
        authenticated = False
        for suffix in (".dds", ".dmr.xml"):
            url = links[0] + suffix
            response = requests.get(url, headers=headers, timeout=40)
            authenticated = response.status_code == 200 and valid_descriptor(response.text, suffix)
            attempts.append({"request_url": url, "http_status": response.status_code,
                             "final_host": urlparse(response.url).hostname,
                             "descriptor_format": suffix,
                             "valid_descriptor": authenticated,
                             "diagnostic": None if authenticated else public_diagnostic(response, token)})
            if authenticated or response.status_code != 400:
                break
        if authenticated:
            descriptor = response.text.replace(token, "[REDACTED]") if token else response.text
            write_json_atomic(self.store.root / "discovery" / "gldas-descriptor.json",
                              {"request_url": url, "fetched_at": utc_now(), "format": suffix,
                               "descriptor": descriptor})
        result = {"product": PRODUCT, "version": VERSION, "collection_id": collection["id"],
                  "fetched_at": utc_now(), "request_url": url, "http_status": response.status_code,
                  "final_host": urlparse(response.url).hostname, "token_configured": bool(token),
                  "authenticated_metadata_access": authenticated, "data_extraction_verified": False,
                  "descriptor_format": suffix, "attempts": attempts,
                  "variables_available": [], "records": 0,
                  "extraction_options": ["Earthdata Cloud OPeNDAP constrained point request", "Harmony HOSS spatial/variable subset"],
                  "legacy_access": "hydro1 retired; HTTP 410 observed"}
        write_json_atomic(self.store.root / "discovery" / "gldas-access-latest.json", result)
        return result

    def fetch(self, city, variables, period, *, force=False):
        if not set(variables) <= set(VARIABLES):
            raise ValueError("Variable GLDAS no catalogada")
        from services.providers.gldas_points import GldasPointClient
        from services.providers.giovanni import GiovanniMonthlyClient
        if not force:
            from services.providers.gldas_points import POLICY
            native = [self.store.read(self.store.query("gldas", PRODUCT, VERSION, v, city, period, POLICY)) for v in variables]
            if native and all(native):
                return native
            cached = GiovanniMonthlyClient(self.store,"gldas").cached(city,variables,period)
            if cached:
                return cached
        if self._points is None:
            self._points = GldasPointClient(self.store)
        return self._points.fetch(city, variables, period, force=force)
