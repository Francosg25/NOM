"""Public JE product categories, explicitly incomplete and never legal decisions."""
from sqlalchemy import select
from .models import Audit, CatalogItem
from .operations import enqueue_reevaluation

PUBLIC_CATEGORIES = [
    ('Motores', 'Motores CA', ['motor eléctrico', 'motores eléctricos'], ['AC motor', 'AC motors', 'motor monofásico'],
     ['NOM-014-ENER-2025'], 'https://www.johnsonelectric.com/'),
    ('Motores', 'Motores CC', ['motor eléctrico', 'motores eléctricos'], ['DC motor', 'DC motors', 'corriente continua'],
     [], 'https://www.johnsonelectric.com/'),
    ('Actuadores', 'Actuadores automotrices', ['actuador', 'actuadores'], ['actuator', 'actuators'],
     [], 'https://www.johnsonelectric.com/en/products/actuators-automotive'),
    ('Bombas y válvulas', 'Bombas y válvulas', ['bomba', 'bombas', 'válvula', 'válvulas'], ['pump', 'pumps', 'valve', 'valves'],
     [], 'https://www.johnsonelectric.com/'),
]


def seed_catalog(db):
    existing = list(db.scalars(select(CatalogItem)))
    keys = {c.technical.get('pilot_key'):c for c in existing if c.technical}
    count = 0
    for family, category, words, synonyms, norms, url in PUBLIC_CATEGORIES:
        parent = None
        for kind, key, name in [('familia','family:'+family,family), ('subfamilia','sub:'+category,category),
                                ('producto','product:'+category,category+' · ficha por completar')]:
            item = keys.get(key)
            if item is None:
                item = CatalogItem(kind=kind,parent_id=parent.id if parent else None,
                    name='MUESTRA PÚBLICA · '+name,
                    description='Categoría pública de Johnson Electric para preparar el piloto. No representa un PN ni inventario confirmado de JE México.',
                    technical={'pilot_key':key,'provenance_url':url,'catalog_status':'borrador_publico'},
                    keywords=words if kind == 'subfamilia' else [], synonyms=synonyms if kind == 'subfamilia' else [],
                    watched_norms=norms if kind == 'subfamilia' else [],active=True)
                db.add(item); db.flush()
                db.add(Audit(actor='cli-operador',action='cargar_muestra_publica',entity_type='catalog',entity_id=str(item.id),
                    after={'provenance_url':url,'status':'borrador_publico','applicability':'sin_evaluar'}))
                keys[key] = item
                enqueue_reevaluation(db,item.id,'cli-operador')
                count += 1
            parent = item
    db.commit()
    return count
