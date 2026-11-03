from __future__ import annotations

import io
import ipaddress
import re
import socket
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable
from urllib.parse import parse_qs, parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from ..network import connection_issue, https_proxy_configured, verified_tls_context


class CollectionError(RuntimeError):
    """Failure is visible and retryable; never equivalent to no changes."""


HOSTS = {
    "dof": {"www.dof.gob.mx", "dof.gob.mx", "sidof.segob.gob.mx"},
    "platiica": {"platiica.economia.gob.mx"},
    "snice": {"www.snice.gob.mx", "snice.gob.mx"},
    "sidof": {"sidof.segob.gob.mx"},
}
ALL_HOSTS = set().union(*HOSTS.values())
USER_AGENT = "JE-NOM-Monitor/0.1 (+internal regulatory review; bounded retrieval)"
MAX_BYTES = 12 * 1024 * 1024


@dataclass
class Document:
    official_id: str
    url: str
    title: str
    content: str
    published_on: date | None = None
    kind: str = "clasificacion_pendiente"
    raw: bytes = b""
    media_type: str = "text/html"
    processing_note: str | None = None
    links: list[str] = field(default_factory=list)


@dataclass
class Batch:
    documents: list[Document]
    complete: bool
    continuation: dict | None
    coverage: str
    errors: list[str] = field(default_factory=list)
    checks: list[dict] = field(default_factory=list)


@dataclass
class FetchResult:
    body: bytes
    media_type: str = "text/html"
    url: str = ""


def validate_url(url: str, kind: str | None = None, *, resolve_dns: bool = False) -> str:
    """Exact official HTTPS hosts, no userinfo/custom ports or private addresses.

    DNS checks are made immediately before live requests, never used to authorize
    an arbitrary host. Deploy egress restrictions too: a proxy resolves names itself.
    """
    try:
        p = urlsplit(url)
        allowed = HOSTS.get(kind, ALL_HOSTS) if kind else ALL_HOSTS
        if (p.scheme != "https" or p.hostname not in allowed or p.username or p.password
                or p.port not in (None, 443) or "\\" in url or any(ord(c) < 32 for c in url)):
            raise ValueError("Destino fuera de las fuentes HTTPS permitidas")
        if resolve_dns:
            addresses = socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                raise ValueError("El destino no resuelve exclusivamente a direcciones públicas")
    except socket.gaierror as exc:
        raise CollectionError(f"[DNS_ERROR] No se pudo resolver el nombre del sitio oficial ({p.hostname}).") from exc
    except (ValueError, OSError) as exc:
        raise CollectionError(f"URL no permitida o DNS no verificable: {urlsplit(url).hostname or 'sin host'}") from exc
    return url


def normalize_url(url: str) -> str:
    validate_url(url)
    p = urlsplit(url)
    host = p.hostname.lower()
    if host == "dof.gob.mx":
        host = "www.dof.gob.mx"
    if host == "snice.gob.mx":
        host = "www.snice.gob.mx"
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    # DOF codigo identifies the publication independently of date/navigation parameters.
    if p.path.endswith("nota_detalle.php"):
        code = parse_qs(p.query).get("codigo", [])
        if code and re.fullmatch(r"\d+", code[0]):
            query = [("codigo", code[0])]
    return urlunsplit(("https", host, p.path or "/", urlencode(sorted(query)), ""))


class SafeFetcher:
    """TLS verified, robots-aware, rate-limited HTTP client; redirects revalidated."""

    def __init__(self, *, client: httpx.Client | None = None, interval: float = 1.0,
                 resolve_dns: bool | None = None, max_bytes: int = MAX_BYTES, attempts: int = 3):
        if resolve_dns is None:
            from ..config import get_settings
            proxy_dns = get_settings().source_dns_mode == 'proxy'
            if proxy_dns and not https_proxy_configured():
                raise CollectionError('[PROXY_CONFIGURATION] SOURCE_DNS_MODE=proxy requiere un proxy HTTPS configurado en el entorno o sistema')
            resolve_dns = not proxy_dns
        if client is not None:
            self.client = client
        else:
            try:
                context = verified_tls_context()
            except (OSError, ValueError) as exc:
                raise CollectionError('[TLS_CONFIGURATION] No se pudo cargar la configuración de certificados HTTPS. Ejecuta PREPARAR_LOCAL.cmd para actualizar dependencias y revisa SSL_CERT_FILE y SSL_CERT_DIR si están configurados.') from exc
            try:
                self.client = httpx.Client(verify=context, trust_env=True,
                    timeout=httpx.Timeout(20, connect=10), follow_redirects=False,
                    headers={"User-Agent": USER_AGENT, "Accept-Encoding":"identity"})
            except (ValueError, httpx.InvalidURL) as exc:
                raise CollectionError('[PROXY_CONFIGURATION] No se pudo iniciar el cliente HTTPS. Revisa el formato del proxy configurado.') from exc
        self._owns_client = client is None
        self.interval = interval
        self.resolve_dns = resolve_dns
        self.max_bytes = max_bytes
        self.attempts = max(1, min(attempts, 3))
        self._last_request = 0.0
        self._robots: dict[str, RobotFileParser] = {}

    def close(self):
        if self._owns_client:
            self.client.close()

    def _request(self, url: str) -> httpx.Response:
        validate_url(url, resolve_dns=self.resolve_dns)
        for attempt in range(self.attempts):
            delay = self.interval - (time.monotonic() - self._last_request)
            if delay > 0:
                time.sleep(delay)
            self._last_request = time.monotonic()
            try:
                with self.client.stream("GET", url) as response:
                    if response.status_code in {429, 502, 503, 504} and attempt < self.attempts - 1:
                        time.sleep(min(2 ** attempt, 4))
                        continue
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > self.max_bytes:
                            raise CollectionError("Respuesta supera el límite de 12 MiB; procesamiento pendiente")
                    # Return a detached response after the bounded stream closes.
                    headers = dict(response.headers)
                    # iter_bytes already decoded HTTP compression. Do not decode twice.
                    headers.pop('content-encoding', None)
                    headers.pop('content-length', None)
                    return httpx.Response(response.status_code, headers=headers,
                                          content=bytes(content), request=response.request)
            except httpx.TransportError as exc:
                issue = connection_issue(exc)
                if not issue.retryable or attempt == self.attempts - 1:
                    raise CollectionError(f"[{issue.code}] {issue.message} ({urlsplit(url).hostname}).") from exc
        raise CollectionError("Consulta agotó los reintentos")

    def _allowed(self, url: str):
        p = urlsplit(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in self._robots:
            robots_url = origin + "/robots.txt"
            response = self._request(robots_url)
            parser = RobotFileParser(robots_url)
            if response.status_code == 404:
                parser.parse([])  # RFC 9309 unavailable (404): no declared rules.
                parser.allow_all = True
            elif response.status_code == 200:
                if re.search(r"<\s*(?:html|!doctype)", response.text, re.I):
                    raise CollectionError("robots.txt devolvió HTML en vez de reglas; consulta suspendida")
                parser.parse(response.text.splitlines())
            else:
                raise CollectionError(f"robots.txt no verificable (HTTP {response.status_code}); consulta suspendida")
            self._robots[origin] = parser
        parser = self._robots[origin]
        if not parser.can_fetch(USER_AGENT, url):
            raise CollectionError("robots.txt no permite esta consulta")
        # Honor explicit delay when present, with bounded scheduling instead of a long sleep.
        delay = parser.crawl_delay(USER_AGENT) or parser.crawl_delay("*")
        if delay and delay > 30:
            raise CollectionError("robots.txt requiere intervalo mayor a 30 s; configurar programación antes de consultar")
        if delay:
            self.interval = max(self.interval, delay)

    def __call__(self, url: str) -> FetchResult:
        for _ in range(4):
            validate_url(url)
            self._allowed(url)
            response = self._request(url)
            if response.is_redirect:
                target = response.headers.get("location")
                if not target:
                    raise CollectionError("Redirección sin destino")
                next_url = urljoin(url, target)
                # Redirects cannot change the selected official source, including to another official agency.
                original_kind = next((k for k, hosts in HOSTS.items() if urlsplit(url).hostname in hosts), None)
                validate_url(next_url, original_kind)
                url = next_url
                continue
            if response.status_code != 200:
                raise CollectionError(f"Consulta oficial falló: HTTP {response.status_code} ({urlsplit(url).hostname})")
            return FetchResult(response.content, response.headers.get("content-type", "text/html").split(";")[0], url)
        raise CollectionError("Demasiadas redirecciones")


def _soup(raw: bytes) -> BeautifulSoup:
    soup = BeautifulSoup(raw, "html.parser")
    if soup.title and re.search(r"captcha|access denied|acceso denegado|just a moment", soup.title.get_text(), re.I):
        raise CollectionError("La fuente requiere intervención humana o bloquea la consulta")
    return soup


def _kind(title: str) -> str:
    pairs = [(r"\bproyecto\b|\bPROY-NOM", "proyecto"),
             (r"cancelaci[oó]n|se cancela", "cancelacion"),
             (r"modificaci[oó]n|modifica", "modificacion"),
             (r"\bacuerdo\b", "acuerdo"), (r"\baviso\b", "aviso"),
             (r"norma oficial mexicana", "norma_definitiva")]
    return next((kind for pattern, kind in pairs if re.search(pattern, title, re.I)), "clasificacion_pendiente")


def _publication_date(soup: BeautifulSoup, text: str) -> date | None:
    # Only explicit publication fields, never first-seen date or arbitrary body dates.
    for meta in soup.select('meta[property="article:published_time"], meta[name="datePublished"], time[itemprop="datePublished"]'):
        value = meta.get("content") or meta.get("datetime") or ""
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            pass
    match = re.search(r"(?:DOF\s*:|[Ff]echa de publicaci[oó]n(?: en el DOF)?\s*:)\s*(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if match:
        try:
            return date(int(match[3]), int(match[2]), int(match[1]))
        except ValueError:
            pass
    return None


def extract_document(url: str, result: FetchResult, title_hint: str = "") -> Document:
    url = normalize_url(url)
    p = urlsplit(url)
    code = parse_qs(p.query).get("codigo", [])
    if code and result.url and p.hostname in HOSTS["dof"]:
        final_code = parse_qs(urlsplit(result.url).query).get("codigo", [])
        if final_code != code:
            raise CollectionError("La nota DOF redirigió a otro identificador o a una portada; revisión pendiente")
    # Known official IDs first; stable URL identity otherwise (not a fabricated legal identifier).
    identifier = f"DOF:{code[0]}" if code and p.hostname in HOSTS["dof"] else "URL:" + url
    sidof_id = re.fullmatch(r'/notas/(?:docFuente/)?(\d+)/?', p.path) if p.hostname == 'sidof.segob.gob.mx' else None
    if sidof_id:
        identifier = f"DOF:{sidof_id[1]}"
        if result.url and urlsplit(result.url).path.rstrip('/') != p.path.rstrip('/'):
            raise CollectionError('SIDOF redirigió a otro documento; revisión pendiente')
    if result.media_type == "application/pdf" or result.body.startswith(b"%PDF-"):
        note = None
        content = ""
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(result.body))
            if len(reader.pages) > 150:
                note = "PDF mayor a 150 páginas: extracción parcial; revisión manual pendiente"
            content = "\n".join(page.extract_text() or "" for page in reader.pages[:150]).strip()
            if not content:
                note = "PDF sin texto extraíble: OCR o revisión manual pendiente"
        except Exception:
            note = "PDF no procesable: conservar referencia y revisar manualmente"
        title = title_hint or p.path.rsplit("/", 1)[-1] or "Documento PDF"
        return Document(identifier, url, title, content, kind=_kind(title), raw=result.body,
                        media_type="application/pdf", processing_note=note)
    if result.media_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
        return Document(identifier, url, title_hint or "Documento pendiente", "", raw=result.body,
                        media_type=result.media_type,
                        processing_note="Formato sin extractor: revisión manual pendiente")
    soup = _soup(result.body)
    date_text = soup.get_text(" ", strip=True)
    published = _publication_date(soup, date_text)
    title_node = next((n for selector in ('h1','h2','title') for n in soup.select(selector) if n.get_text(strip=True)), None)
    title = title_hint or (title_node.get_text(" ", strip=True) if title_node else "Documento sin título")
    for node in soup.select("script, style, nav, header, footer, form, noscript, .menu, .navigation, .breadcrumb"):
        node.decompose()
    known_node = None
    if sidof_id and p.path.startswith('/notas/docFuente/') and soup.h1 and re.search(r'norma|acuerdo|aviso|decreto|resoluci',soup.h1.get_text(),re.I):
        known_node = soup.body
    if p.hostname in HOSTS['snice'] and p.path.endswith('seguridad.normatividad.html'):
        heading = next((h for h in soup.select('h2') if 'Normatividad' in h.get_text()),None)
        if heading: known_node = heading.find_parent(class_='col-md-12')
    node = (known_node or soup.select_one("#DivDetalle") or soup.select_one(".DetaDoc") or
            soup.select_one("article") or soup.select_one("main") or soup.body or soup)
    content = "\n".join(line.strip() for line in node.get_text("\n", strip=True).splitlines() if line.strip())
    if not content:
        raise CollectionError("Documento HTML sin contenido útil; no se registra como versión vacía")
    note = None if known_node is not None or node is not soup.body and node is not soup else "Extracción general HTML: revisar posible ruido de navegación"
    links = set()
    for anchor in node.select('a[href]'):
        target = urljoin(url, str(anchor['href']))
        try:
            links.add(normalize_url(target))
        except CollectionError:
            continue
    return Document(identifier, url, title, content, published, _kind(title), result.body,
                    result.media_type, note, sorted(links))


def _index_links(url: str, result: FetchResult, day: date) -> tuple[list[dict], list[str], bool]:
    soup = _soup(result.body)
    docs: dict[str, dict] = {}
    indexes: set[str] = set()
    for link in soup.select("a[href]"):
        target = urljoin(url, str(link["href"]))
        try:
            validate_url(target, "dof")
        except CollectionError:
            continue
        p = urlsplit(target)
        q = parse_qs(p.query)
        if p.path.endswith("nota_detalle.php") and re.fullmatch(r"\d+", q.get("codigo", [""])[0]):
            target = normalize_url(target)
            docs.setdefault(target, {"url": target, "title": link.get_text(" ", strip=True)})
        elif p.path.endswith("index.php") and p.query:
            try:
                same_day = (q.get("year", [str(day.year)])[0] == str(day.year)
                            and int(q.get("month", [str(day.month)])[0]) == day.month
                            and int(q.get("day", [str(day.day)])[0]) == day.day)
            except ValueError:
                continue  # A malformed calendar link does not discard valid notes.
            # Only same-day index pagination/edition links. Never follow the calendar into other periods.
            if same_day and (all(k in q for k in ("year", "month", "day"))
                             or any(k in q for k in ("edicion", "edition", "page", "pagina", "pag"))):
                indexes.add(normalize_url(target))
    explicit_empty = bool(re.search(r"no (?:se public[oó]|hay publicaciones|existe publicaci[oó]n)|sin publicaci[oó]n", soup.get_text(" "), re.I))
    return list(docs.values()), sorted(indexes), explicit_empty


def collect(kind: str, urls: list[str], period_start: date, period_end: date,
            continuation: dict | None = None, limit: int = 40, *,
            fetcher: Callable[[str], FetchResult] | None = None) -> Batch:
    """Collect a bounded unit, retaining queues across errors and resource limits.

    Inject a callable returning FetchResult in tests; production always uses SafeFetcher.
    PLATIICA and SNICE are known-document monitors, not unverified discovery feeds.
    """
    kind = kind.lower()
    if kind not in HOSTS:
        raise CollectionError("Tipo de fuente no soportado")
    if period_end < period_start or (period_end - period_start).days > 366:
        raise CollectionError("Periodo inválido: seleccionar como máximo 367 días por trabajo")
    if not 1 <= limit <= 200:
        raise CollectionError("Límite de documentos debe estar entre 1 y 200")
    for url in urls:
        validate_url(url, kind)
    if not urls:
        raise CollectionError("Fuente sin URLs configuradas; cobertura pendiente")
    if kind == "dof" and len(urls) != 1:
        raise CollectionError("DOF requiere un único índice base; no se ignorarán URLs adicionales")
    if kind == 'sidof' and any('/dof/sidof' in urlsplit(u).path for u in urls):
        from .sidof import collect_daily, validate_api_urls
        validate_api_urls(urls)
        return collect_daily(urls, period_start, period_end, continuation, limit, fetcher=fetcher)
    if kind in {"platiica", "snice"} and any(urlsplit(u).path in {"", "/"} for u in urls):
        raise CollectionError("Configurar fichas o publicaciones concretas; una portada no es un canal de descubrimiento")
    if continuation and (continuation.get("kind") != kind or continuation.get("start") != period_start.isoformat()
                         or continuation.get("end") != period_end.isoformat()):
        raise CollectionError("El punto de continuación pertenece a otra fuente o periodo")
    state = dict(continuation or {
        "v": 1, "kind": kind, "start": period_start.isoformat(), "end": period_end.isoformat(),
        "day": period_start.isoformat(), "pending": [], "indexes": [], "visited_indexes": [], "seen": [],
        "known_loaded": False,
    })
    # Copy nested lists to avoid mutating a caller's persisted JSON state before commit.
    for key in ("pending", "indexes", "visited_indexes", "seen"):
        state[key] = list(state.get(key, []))
    output: list[Document] = []
    errors: list[str] = []
    own_fetcher = fetcher is None
    client = SafeFetcher() if own_fetcher else fetcher
    requests = 0
    max_requests = max(10, min(100, limit * 2))
    coverage = ("DOF: índices diarios HTML y enlaces explícitos a notas, paginación y ediciones; "
                "sin garantía de índices omitidos, ediciones no enlazadas ni documentos publicados fuera del periodo. "
                "Validación en vivo pendiente en esta instalación."
                if kind == "dof" else f"{kind.upper()}: seguimiento de URLs concretas configuradas; "
                "no descubre todo el sitio ni garantiza publicaciones nuevas. Validación en vivo pendiente.")
    done = False
    try:
        while len(output) < limit and requests < max_requests:
            if state["pending"]:
                item = state["pending"][0]
                result = client(item["url"])
                requests += 1
                document = extract_document(item["url"], result, item.get("title", ""))
                if kind == 'dof' and document.published_on and not period_start <= document.published_on <= period_end:
                    raise CollectionError('La nota DOF tiene fecha fuera del periodo solicitado; comprobar índice o redirección')
                output.append(document)
                state["pending"].pop(0)
                state["seen"].append(item["url"])
                continue
            if kind != "dof":
                if state["known_loaded"]:
                    done = True
                    break
                state["pending"] = [{"url": normalize_url(u), "title": ""} for u in dict.fromkeys(urls)]
                state["known_loaded"] = True
                continue
            day = date.fromisoformat(state["day"])
            if day > period_end:
                done = True
                break
            if not state["indexes"] and not state["visited_indexes"]:
                # A configured DOF index establishes the host/path, not an invented API.
                base = urlsplit(urls[0])
                if base.hostname not in {"www.dof.gob.mx", "dof.gob.mx"} or not base.path.endswith("index.php"):
                    raise CollectionError("Descubrimiento DOF requiere URL oficial /index.php; SIDOF no se presupone compatible")
                state["indexes"] = [urlunsplit(("https", base.netloc, base.path,
                                               urlencode({"year": day.year, "month": day.month, "day": day.day}), ""))]
            if state["indexes"]:
                url = state["indexes"][0]
                result = client(url)
                requests += 1
                docs, indexes, explicit_empty = _index_links(url, result, day)
                # A self-link or a previously visited page is not evidence that an
                # otherwise empty/unknown index has been covered.
                indexes = [u for u in indexes if u != normalize_url(url) and u not in state['visited_indexes']]
                if not docs and not indexes and not explicit_empty:
                    raise CollectionError("Índice DOF sin notas ni ausencia explícita: estructura desconocida; periodo pendiente")
                state["indexes"].pop(0)
                state["visited_indexes"].append(normalize_url(url))
                state["indexes"].extend(u for u in indexes if u not in state["visited_indexes"] and u not in state["indexes"])
                waiting = {item["url"] for item in state["pending"]}
                state["pending"].extend(item for item in docs if item["url"] not in state["seen"] and item["url"] not in waiting)
                continue
            # Every discovered edition/index and document for this day has been consumed.
            state["day"] = (day + timedelta(days=1)).isoformat()
            state["visited_indexes"] = []
        # Queue exhaustion on the exact limit is recognized by a cheap follow-up iteration;
        # retaining a continuation is conservative and never drops an unprocessed item.
    except (CollectionError, httpx.HTTPError, ValueError) as exc:
        errors.append(str(exc))
    finally:
        if own_fetcher:
            client.close()
    return Batch(output, done, None if done else state, coverage, errors)
