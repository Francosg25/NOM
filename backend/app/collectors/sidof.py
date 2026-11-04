"""Date-based SIDOF discovery. HTML pages remain available as reference monitors."""
from copy import deepcopy
from datetime import date, datetime, timedelta
import hashlib
import json
import re
import unicodedata

from bs4 import BeautifulSoup

from .core import Batch, CollectionError, Document, SafeFetcher, _kind

API_BASE = 'https://sidof.segob.gob.mx/dof/sidof'
EDITIONS = {'Matutina':'NotasMatutinas', 'Vespertina':'NotasVespertinas', 'Extraordinaria':'NotasExtraordinarias'}


def is_daily(urls):
    return len(urls) == 1 and urls[0].rstrip('/') == API_BASE


def validate_api_urls(urls):
    if not is_daily(urls):
        raise CollectionError('SIDOF diario requiere únicamente la base oficial https://sidof.segob.gob.mx/dof/sidof')


def _text(value):
    return BeautifulSoup(value or '', 'html.parser').get_text(' ', strip=True).replace('\u00ad', '')


def relevant(title):
    title = re.sub(r'[\u2010-\u2015\u2212]', '-', unicodedata.normalize('NFKC', title).replace('\u00ad', ''))
    if re.match(r'^\s*NMX[-\s]', title, re.I):
        return False
    return bool(re.search(r'\b(?:PROY[-\s]*)?NOM[-\s]\w|\bnormas?\s+oficial(?:es)?\s+mexican[ao]s?|anexo\s*2\s*\.\s*4\s*\.\s*1|reglas?\s+y\s+criterios?.{0,120}comercio\s+exterior', title, re.I))


def _id(value, label):
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]{1,12}', str(value)):
        raise CollectionError(f'SIDOF: {label} inválido; revisión pendiente')
    return str(value)


def _date(value):
    try:
        return datetime.strptime(value, '%d-%m-%Y').date()
    except (TypeError, ValueError) as exc:
        raise CollectionError('SIDOF: fecha de publicación ausente o inválida') from exc


def _json(result):
    try:
        data = json.loads(result.body)
    except (ValueError, UnicodeError) as exc:
        raise CollectionError('SIDOF: respuesta no es JSON válido') from exc
    if not isinstance(data, dict) or data.get('messageCode') != 200 or data.get('response') != 'OK':
        raise CollectionError('SIDOF: el servicio no confirmó una respuesta exitosa')
    return data


def _document(result, expected, day):
    payload = _json(result)
    note = payload.get('Nota')
    if isinstance(note, list) and len(note) == 1:
        note = note[0]
    if not isinstance(note, dict):
        raise CollectionError('SIDOF: detalle de nota ausente o ambiguo')
    code = _id(note.get('codNota'), 'código de nota')
    if code != expected['id'] or _date(note.get('fecha')) != day or _id(note.get('codDiario'), 'diario') != expected['diary']:
        raise CollectionError('SIDOF: el detalle no corresponde al código, fecha y diario solicitados')
    if payload.get('tamanioExcesivo') is True or note.get('tamanioExcesivo') is True:
        raise CollectionError(f'SIDOF: contenido marcado como parcial para DOF:{code}')
    html = note.get('cadenaContenido') or note.get('contenido')
    if not isinstance(html, str) or not html.strip():
        html = note.get('contenidoTxt')
    if not isinstance(html, str) or not html.strip():
        title = _text(note.get('titulo')) or expected.get('title', '')
        if relevant(title):
            return Document(f'DOF:{code}', f'https://sidof.segob.gob.mx/notas/docFuente/{code}',
                title, '', day, _kind(title), raw=result.body, media_type='application/json',
                processing_note='SIDOF solo ofrece imagen/PDF para esta nota; texto y aplicabilidad pendientes de revisión.')
        return {'id':f'DOF:{code}', 'url':f'https://sidof.segob.gob.mx/notas/docFuente/{code}',
                'reason':'Sin título ni texto extraíble; no se pudo descartar relevancia NOM.',
                'detail_sha256':hashlib.sha256(result.body).hexdigest()}
    soup = BeautifulSoup(html, 'html.parser')
    for node in soup.select('script,style,nav,header,footer,form'):
        node.decompose()
    content = soup.get_text('\n', strip=True).strip()
    if not content:
        raise CollectionError(f'SIDOF: contenido vacío para DOF:{code}')
    title = _text(note.get('titulo')) or expected.get('title', '')
    if not title:
        heading = soup.select_one('h1,h2')
        if heading:
            title = heading.get_text(' ', strip=True)
        else:
            # Source notes with a null JSON title still carry their official
            # heading in the document. Do not silently discard those notes.
            lines = [line.strip() for line in content.splitlines() if len(line.strip()) > 25]
            title = next((line for line in lines[:12] if re.match(r'^(?:NORMA|PROYECTO|ACUERDO|AVISO|DECRETO|RESOLUCI[OÓ]N|CONVENIO|CIRCULAR|SENTENCIA|DECLARATORIA)\b', line, re.I)), '')
    if not title:
        return {'id':f'DOF:{code}', 'url':f'https://sidof.segob.gob.mx/notas/docFuente/{code}',
                'reason':'Texto disponible sin encabezado identificable; clasificación NOM pendiente.',
                'detail_sha256':hashlib.sha256(result.body).hexdigest()}
    if not relevant(title):
        return None
    kind = ('cancelacion' if re.search(r'cancelaci[oó]n', title, re.I) else
            'modificacion' if re.search(r'modificaci[oó]n|modifica', title, re.I) else _kind(title))
    return Document(f'DOF:{code}', f'https://sidof.segob.gob.mx/notas/docFuente/{code}',
                    title, content, day, kind, raw=result.body, media_type='application/json')


def _load_day(client, day):
    stamp = day.strftime('%d-%m-%Y')
    manifest_result = client(f'{API_BASE}/diarios/porFecha/{stamp}')
    manifest = _json(manifest_result)
    diary_groups = {}
    for edition in EDITIONS:
        rows = manifest.get(edition)
        if edition not in manifest or rows is not None and not isinstance(rows, list):
            raise CollectionError('SIDOF: estructura de ediciones desconocida')
        if any(not isinstance(row, dict) for row in rows or []):
            raise CollectionError('SIDOF: diario inválido')
        diary_groups[edition] = {_id(row.get('codDiario'), 'diario') for row in rows or []}
    listing_result = client(f'{API_BASE}/notas/{stamp}')
    listing = _json(listing_result)
    indexed, pending = {}, []
    for edition, group in EDITIONS.items():
        if not isinstance(listing.get(group), list):
            raise CollectionError('SIDOF: falta una lista de notas por edición')
        for row in listing[group]:
            if not isinstance(row, dict):
                raise CollectionError('SIDOF: nota del índice inválida')
            code, diary = _id(row.get('codNota'), 'nota'), _id(row.get('codDiario'), 'diario de la nota')
            if _date(row.get('fecha')) != day or diary not in diary_groups[edition]:
                raise CollectionError('SIDOF: nota fuera de fecha o de las ediciones declaradas')
            identity = {'id':code, 'diary':diary}
            if code in indexed:
                if indexed[code] != identity:
                    raise CollectionError('SIDOF: una nota aparece con identidades contradictorias')
                continue
            indexed[code] = identity
            title = _text(row.get('titulo'))
            if not title or relevant(title):
                pending.append({**identity, 'title':title})
    if len(indexed) > 10000:
        raise CollectionError('SIDOF: índice excede el límite de notas por día')
    diaries = sorted(set().union(*diary_groups.values()))
    absence, calendar_hash = False, None
    if not diaries and not indexed:
        calendar_result = client(f'{API_BASE}/diarios/{day.year}')
        calendar = _json(calendar_result)
        if not isinstance(calendar.get('FechasSinPublicacion'), list) or stamp not in calendar['FechasSinPublicacion']:
            raise CollectionError('SIDOF: respuesta vacía sin declaración explícita de ausencia de publicación')
        absence, calendar_hash = True, hashlib.sha256(calendar_result.body).hexdigest()
    elif not indexed or any(diary not in {i['diary'] for i in indexed.values()} for diary in diaries):
        raise CollectionError('SIDOF: hay ediciones declaradas sin sus notas; revisión incompleta')
    return pending, {'day':str(day), 'diary_ids':diaries,
        'notes_checked':len(indexed), 'details_required':len(pending), 'selected_ids':[], 'unresolved':[],
        'declared_no_publication':absence, 'calendar_sha256':calendar_hash,
        'manifest_sha256':hashlib.sha256(manifest_result.body).hexdigest(),
        'index_sha256':hashlib.sha256(listing_result.body).hexdigest()}


def collect_daily(urls, start, end, continuation, limit, *, fetcher=None):
    validate_api_urls(urls)
    if continuation and (continuation.get('mode') != 'sidof_api_v1' or
            continuation.get('start') != str(start) or continuation.get('end') != str(end)):
        raise CollectionError('El cursor no pertenece a esta consulta diaria SIDOF')
    state = deepcopy(continuation or {'mode':'sidof_api_v1', 'kind':'sidof', 'start':str(start),
        'end':str(end), 'queue':[{'day':str(end - timedelta(days=i)), 'pending':[], 'loaded':False, 'check':None}
            for i in range((end - start).days + 1)]})
    try:
        if not isinstance(state['queue'], list): raise ValueError()
        days = [date.fromisoformat(item['day']) for item in state['queue']]
        if len(days) != len(set(days)) or any(not start <= day <= end for day in days): raise ValueError()
    except (KeyError, ValueError, TypeError) as exc:
        raise CollectionError('Cursor SIDOF sin fechas válidas dentro del periodo') from exc
    own = fetcher is None
    client = SafeFetcher() if own else fetcher
    calls, documents, checks, errors, deferred = 0, [], [], [], []
    max_calls = min(40, max(10, limit * 2))
    try:
        while state['queue'] and len(documents) < limit and calls < max_calls:
            current = state['queue'][0]
            day = date.fromisoformat(current['day'])
            try:
                if not current['loaded']:
                    if calls + 3 > max_calls: break
                    calls += 3  # index loading uses at most three requests
                    pending, check = _load_day(client, day)
                    current.update(loaded=True, pending=pending, check=check)
                elif current['pending']:
                    item = current['pending'][0]
                    code = _id(item['id'], 'código de cursor')
                    calls += 1
                    doc = _document(client(f'{API_BASE}/notas/nota/{code}'), item, day)
                    if isinstance(doc, dict):
                        current['check']['unresolved'].append(doc)
                    elif doc:
                        documents.append(doc)
                        current['check']['selected_ids'].append(doc.official_id)
                        if doc.processing_note:
                            current['check']['unresolved'].append({'id':doc.official_id, 'url':doc.url, 'reason':doc.processing_note})
                    current['pending'].pop(0)
                if current['loaded'] and not current['pending']:
                    checks.append(current['check'])
                    state['queue'].pop(0)
            except (CollectionError, ValueError, KeyError, TypeError) as exc:
                # Keep the failed date/detail intact, while allowing other dates
                # to deliver their valid publications. Never infer an empty day.
                errors.append(f'{day}: {exc}')
                current['failed'] = True
                deferred.append(state['queue'].pop(0))
    finally:
        state['queue'].extend(deferred)
        if own: client.close()
    complete = not state['queue']
    coverage = ('SIDOF API: consulta por fecha de ediciones y notas; selección de NOM, proyectos, modificaciones, '
        'cancelaciones y reglas de comercio exterior por título, revisando también notas sin título. '
        'Registros sin texto/título se conservan como referencias pendientes en el registro de consulta. '
        'No determina aplicabilidad a productos ni acredita cobertura normativa integral. '
        f'En este lote: {len(checks)} días consultados y {len(documents)} publicaciones seleccionadas; '
        f'{sum(len(check["unresolved"]) for check in checks)} referencias pendientes de revisión.')
    return Batch(documents, complete and not errors, None if complete and not errors else state, coverage, errors, checks)
