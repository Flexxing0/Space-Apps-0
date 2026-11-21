"""Inventario de evidencia del piloto. No construye un mapa de riesgo sin capas."""
def impact_status(city):
    pilot=city['id']=='comodoro-rivadavia'
    return {'city':city,'status':'insufficient_spatial_evidence',
        'summary':'Piloto Comodoro: incidente de 2017 documentado; evaluación espacial de sitios pendiente de capas y licencias verificadas.' if pilot else
            'Sin capas territoriales verificadas para esta ciudad. No se estima riesgo por extrapolación.',
        'layers':[{'name':'Acontecimiento observado: temporal 2017','status':'documented_incident' if pilot else 'not_catalogued',
            'source_url':'https://www.ign.gob.ar/odc-14-Paredes','limitation':'Registro bibliográfico; no es geometría de inundación ni alerta actual.'},
            {'name':'Susceptibilidad geológica SEGEMAR','status':'reference_only',
             'source_url':'https://archivointemin.segemar.gov.ar/handle/308849217/5102',
             'limitation':'Informe verificado; no hay polígonos vectoriales operativos importados. No se inventan intersecciones.'},
            {'name':'Elevación y drenaje IGN','status':'not_integrated','source_url':'https://www.ign.gob.ar/NuestrasActividades/Geodesia/ModeloDigitalElevaciones',
             'limitation':'Faltan descarga, resolución, licencia y derivación hidrológica verificadas.'},
            {'name':'Calles y superficies OpenStreetMap','status':'not_integrated','source_url':'https://www.openstreetmap.org/copyright',
             'limitation':'Datos ODbL; no se infiere calle de tierra ni transitabilidad sin geometría y etiquetas verificadas.'}],
        'geometries':[],'hazard_map_enabled':False,'confirmed_impacts':[]}
