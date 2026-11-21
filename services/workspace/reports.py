"""PDFs a partir de resultados reales; no agrega inferencias causales."""
from io import BytesIO
from html import escape
import json

from services.providers.cache import utc_now


def pdf_report(title,sections,*,points=None,unit=None,comparison_points=None):
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.graphics.shapes import Drawing, Line, String
    buffer=BytesIO();styles=getSampleStyleSheet();story=[]
    def text(value,style='BodyText'):
        story.append(Paragraph(escape(str(value)).replace('\n','<br/>'),styles[style]));story.append(Spacer(1,8))
    text('EarthLens · '+title,'Title');text('Generado: '+utc_now())
    for heading,value in sections:
        text(heading,'Heading2');text(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2))
    if points:
        values=[p['value'] for p in [*points,*(comparison_points or [])] if p['value'] is not None]
        if values:
            # Los huecos cortan la línea; no se rellenan los registros nulos.
            import datetime
            def timestamp(p):return datetime.datetime.fromisoformat(p['date']).timestamp()
            combined=[*points,*(comparison_points or [])]
            first,last=min(timestamp(p) for p in combined),max(timestamp(p) for p in combined);low,high=min(values),max(values)
            drawing=Drawing(470,160);previous=None
            for p in points:
                if p['value'] is None:previous=None;continue
                x=10+440*(timestamp(p)-first)/max(1,last-first);y=20+120*(p['value']-low)/max(1e-12,high-low)
                if previous:drawing.add(Line(*previous,x,y,strokeColor=colors.HexColor('#126f60'),strokeWidth=1))
                previous=(x,y)
            previous=None
            for p in comparison_points or []:
                if p['value'] is None:previous=None;continue
                x=10+440*(timestamp(p)-first)/max(1,last-first);y=20+120*(p['value']-low)/max(1e-12,high-low)
                if previous:drawing.add(Line(*previous,x,y,strokeColor=colors.HexColor('#b06421'),strokeWidth=1))
                previous=(x,y)
            drawing.add(String(10,2,points[0]['date'][:10],fontSize=8));drawing.add(String(360,2,points[-1]['date'][:10],fontSize=8))
            drawing.add(String(10,145,str(unit or ''),fontSize=9));story.append(drawing)
            if comparison_points:text('Verde: ciudad principal. Naranja: segunda ciudad. Misma variable, producto y unidad; no son medias regionales.')
        text('Registros (primeros 40; exportar JSON/CSV para la serie completa)','Heading2')
        rows=[['Fecha','Valor','Unidad']]+[[p['date'],str(p['value']) if p['value'] is not None else 'Sin dato',unit or ''] for p in points[:40]]
        table=Table(rows,repeatRows=1);table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e2eeeb')),
            ('FONTSIZE',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),5)]));story.append(table)
    SimpleDocTemplate(buffer,pagesize=A4,title=title,author='EarthLens · Patagonia Prime').build(story)
    return buffer.getvalue()
