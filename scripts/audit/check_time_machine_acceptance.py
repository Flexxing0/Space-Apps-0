"""Aceptación A–H en Chrome real. Sólo G modifica un pronóstico en memoria de prueba.

La base privada es temporal; los históricos y pronósticos del proveedor son reales.
No se crean usuarios/eventos de demostración en la base del usuario.
"""
from copy import deepcopy
import argparse
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import tempfile
import threading
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server,WSGIRequestHandler

from app import create_app
from scripts.audit.audit_timesfm import audit as audit_timesfm
from services.providers.cache import DEFAULT_CACHE_DIR
from services.events.monitoring import MonitoringService

ROOT=Path('data/cache/reports/time-machine-correction/acceptance')

class QuietHandler(WSGIRequestHandler):
    def log_request(self,*args,**kwargs):pass

def hashes():
    root=DEFAULT_CACHE_DIR.parent
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['power','radar','science/series','science/hydrology']
        for p in (root/folder).rglob('*.json')}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-url',default='http://127.0.0.1:5000')
    parser.add_argument('--isolated',action='store_true',help='Usar sólo el servidor temporal si Docker no está levantado')
    args=parser.parse_args(argv)
    ROOT.mkdir(parents=True,exist_ok=True);before=hashes();errors=[];frames=[];results={};screens=[]
    (ROOT/'report.json').write_text(json.dumps({'status':'running','started_at':datetime.now(timezone.utc).isoformat()}),encoding='utf-8')
    today=datetime.now(timezone.utc).date()
    with tempfile.TemporaryDirectory(prefix='earthlens-acceptance-private-') as temp:
        app=create_app({'DATABASE_PATH':Path(temp)/'private.sqlite3','SECRET_KEY':'temporary-acceptance-session-not-production',
            'SESSION_COOKIE_NAME':'earthlens_acceptance_session'})
        server=make_server('127.0.0.1',5052,app,threaded=True,request_handler=QuietHandler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
                page=browser.new_page(viewport={'width':1512,'height':982})
                page.on('pageerror',lambda error:errors.append(str(error)))
                def capture_response(response):
                    if '/api/workspace/frame?' not in response.url or response.status!=200:return
                    try:frames.append(response.json()['data'])
                    except Exception:pass
                page.on('response',capture_response)
                def wait_frame(day=None,variable=None,kind=None):
                    page.wait_for_function("expected=>document.body.dataset.frameReady==='true' && (!expected.day||document.body.dataset.frameDate.startsWith(expected.day)) && (!expected.variable||document.body.dataset.frameVariable===expected.variable) && (!expected.kind||document.body.dataset.frameKind===expected.kind)",arg={'day':day,'variable':variable,'kind':kind},timeout=120000)
                def shot(name):
                    path=ROOT/(name+'.png');page.screenshot(path=str(path),animations='disabled');screens.append(str(path))
                def read_frame():
                    # Lectura independiente de la selección visible; sin fixtures.
                    data=page.evaluate("""async()=>{const query=new URLSearchParams({city_id:document.querySelector('#city').value,
                      date:document.querySelector('#date').value,variable:document.querySelector('#variable').value,
                      provider:document.querySelector('#source').value,scale:document.querySelector('#scale').value,
                      start:document.querySelector('#start').value,end:document.querySelector('#end').value,
                      mode:document.querySelector('#mode').value});return (await (await fetch('/api/workspace/frame?'+query)).json()).data;}""")
                    if data.get('focus',{}).get('value') is not None:
                        formatted=page.evaluate("v=>new Intl.NumberFormat('es-AR',{maximumFractionDigits:2}).format(v)",data['focus']['value'])
                        assert page.locator('#value').inner_text()==formatted
                        assert formatted in page.locator('.point-value.selected').inner_text()
                    return data
                def toggle_tools():
                    if not page.locator('#tools').is_visible():page.click('#toggle-tools')
                def choose_variable(value):
                    toggle_tools();page.select_option('#variable',value);page.click('#close-tools');wait_frame(variable=value)
                def drag_to(day):
                    desired=datetime.fromisoformat(day).replace(hour=12,tzinfo=timezone.utc).timestamp()*1000
                    axis=page.locator('#scrubber');bounds=axis.bounding_box()
                    data=axis.evaluate('(e)=>({start:+e.dataset.start,end:+e.dataset.end,value:+e.value})')
                    fraction=(desired-data['start'])/(data['end']-data['start']);assert 0<fraction<1
                    x=bounds['x']+8.5+(bounds['width']-17)*fraction
                    current=bounds['x']+8.5+(bounds['width']-17)*data['value']/10000
                    page.mouse.move(current,bounds['y']+bounds['height']/2);page.mouse.down();page.mouse.move(x,bounds['y']+bounds['height']/2,steps=7);page.mouse.up()
                    wait_frame(day=day,kind='forecast')

                public_url='http://127.0.0.1:5052' if args.isolated else args.public_url.rstrip('/')
                page.goto(public_url+'/',wait_until='networkidle');wait_frame(kind='forecast')
                assert not page.locator('#inspector').is_visible();assert not page.locator('#tools').is_visible()
                assert page.locator('#map').bounding_box()['width']>=1511
                timeline=page.locator('.timeline').bounding_box();assert timeline['y']+timeline['height']<=982
                shot('A-inicio');results['A']={'status':'passed','root':'/','map_full_viewport':True,'panels_initially_closed':True}

                choose_variable('PRECTOTCORR');page.locator('#date').fill('2017-03-31T12:00');page.locator('#date').dispatch_event('change')
                wait_frame(day='2017-03-31',kind='reanalysis');page.click('.caption-actions button[data-panel="data"]')
                assert 'POWER_DAILY_AG' in page.locator('#provenance').inner_text()
                historical=read_frame()
                assert historical['record']['provider']=='NASA POWER';assert historical['focus']['value'] is not None
                shot('B-pasado-2017');results['B']={'status':'passed','date':'2017-03-31','provider':'NASA POWER','product':'POWER_DAILY_AG','value':historical['focus']}
                page.click('#close-inspector')

                choose_variable('T2M');page.click('#present');wait_frame(day=today.isoformat(),variable='T2M',kind='forecast')
                for offset in [1,7]:drag_to((today+timedelta(days=offset)).isoformat())
                expected_day=(today+timedelta(days=7)).isoformat()
                future=read_frame()
                assert future['record']['provider']=='Open-Meteo';assert future['focus']['value'] is not None
                assert page.locator('#scrubber').count()==1
                page.click('.caption-actions button[data-panel="data"]');shot('C-futuro-7-dias')
                available=[]
                for variable in ['PRECTOTCORR','precipitation_probability','WS2M','wind_gusts_10m','RH2M','cloud_cover']:
                    choose_variable(variable);wait_frame(day=expected_day,variable=variable,kind='forecast')
                    current=read_frame()
                    assert current['focus']['value'] is not None;available.append(variable)
                choose_variable('T2M')
                results['C']={'status':'passed','same_timeline':True,'drag_days':[1,7],'future_value':future['focus'],
                    'verified_variables':['T2M',*available],'provider':'Open-Meteo','issued_at':future['record']['issued_at'],
                    'uncertainty':future['record'].get('uncertainty')}

                page.click('.top button[data-panel="calendar"]')
                event_day=(today+timedelta(days=3)).isoformat()
                page.locator('#calendar-jump').fill(event_day);page.locator('#calendar-jump').dispatch_event('change')
                wait_frame(day=event_day,kind='forecast')
                page.click('#calendar button[data-day="'+event_day+'"]');wait_frame(day=event_day,kind='forecast')
                assert page.locator('#date').input_value().startswith(event_day)
                assert page.locator('#calendar button.selected').get_attribute('data-day')==event_day
                shot('D-calendario');results['D']={'status':'passed','date':event_day,'navigation_left_map':False}

                if not args.isolated:
                    selection=page.evaluate('location.search')
                    page.goto('http://127.0.0.1:5052/'+selection,wait_until='networkidle');wait_frame(day=event_day,kind='forecast')
                    page.click('.top button[data-panel="calendar"]')
                page.click('#new-event')
                page.locator('#auth-form [name="username"]').fill('acceptance_temporary')
                page.locator('#auth-form [name="password"]').fill('temporary-software-test-password')
                page.click('#auth-form button[name="register"]');page.wait_for_function("!document.querySelector('#account').hidden")
                name='Excursión de aceptación · base temporal'
                form=page.locator('#event-form');form.locator('[name="name"]').fill(name)
                form.locator('[name="start"]').fill(event_day+'T10:00');form.locator('[name="end"]').fill(event_day+'T12:00')
                form.locator('summary').click();form.locator('[name="max_temperature"]').fill('28')
                page.click('#preview-event');page.wait_for_function("document.querySelector('#assessment').textContent.includes('Fechas alternativas')")
                form.locator('button[type="submit"]').click();page.wait_for_function("document.querySelector('#events-list').textContent.includes('aceptación')")
                page.reload(wait_until='networkidle');wait_frame(day=event_day)
                page.wait_for_selector('#time-markers button[data-event]')
                event_id=page.locator('#time-markers button[data-event]').first.get_attribute('data-event')
                page.click('.top button[data-panel="calendar"]')
                assert page.locator('#calendar button[data-day="'+event_day+'"].has-event').count()==1
                assert page.locator('.leaflet-marker-icon').count()>=2  # valor consultado y evento georreferenciado
                page.click('#close-inspector')
                page.click('#time-markers button[data-event="'+event_id+'"]')
                page.wait_for_function("document.querySelector('#event-details').textContent.includes('aceptación') && document.querySelector('#assessment').textContent.includes('Fechas alternativas')")
                assert name in page.locator('#event-details').inner_text()
                assert 'Open-Meteo' in page.locator('#assessment').inner_text()
                shot('E-evento-pronostico');results['E']={'status':'passed','persisted_after_reload':True,'event_markers_calendar_timeline_map':True,'alternatives_visible':True,'database':'temporary_only'}

                page.click('#close-inspector');page.click('.caption-actions button[data-panel="profile"]')
                page.wait_for_function("document.querySelector('#profile-title').textContent==='Comodoro Rivadavia'")
                page.wait_for_function("document.querySelector('#climate-radial') && !!Chart.getChart(document.querySelector('#climate-radial'))",timeout=120000)
                radial=page.locator('#climate-radial').bounding_box();drawer=page.locator('#inspector').bounding_box()
                assert radial['y']>=drawer['y'] and radial['y']+radial['height']<=drawer['y']+drawer['height']
                shot('F-perfil-comodoro');results['F']={'status':'passed','city':'comodoro-rivadavia','radial_real_cached_data':True}

                planning=app.extensions['earthlens_planning'];real=planning.weather.bundle('comodoro-rivadavia')
                monitor=MonitoringService(app.extensions['earthlens_events'],planning)
                weather_before={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in planning.weather.cache.directory.glob('*.json')}
                with patch.object(planning.weather,'bundle',return_value=deepcopy(real)):first=monitor.run(force=True)
                simulated=deepcopy(real);simulated.update(provider='SIMULACION_SOLO_PRUEBA',product='synthetic_acceptance_test',fetched_at=datetime.now(timezone.utc).isoformat())
                for point in simulated['variables']['temperature_2m']['series']:
                    if point['value'] is not None:point['value']=40.0
                with patch.object(planning.weather,'bundle',return_value=simulated):
                    changed=monitor.run(force=True);repeated=monitor.run(force=True)
                assert first['summary']['notifications']==1 and changed['summary']['notifications']==1 and repeated['summary']['notifications']==0
                assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in weather_before.items())
                page.click('.top button[data-panel="notifications"]');page.wait_for_function("document.querySelectorAll('#notifications-list .card').length===2")
                assert '40' in page.locator('#notifications-list').inner_text()
                page.locator('#notifications-list [data-notification-event]').first.click()
                page.wait_for_function("document.querySelector('#event-details').textContent.includes('aceptación')")
                assert page.locator('#city').input_value()=='comodoro-rivadavia';assert page.locator('#date').input_value().startswith(event_day)
                results['G']={'status':'passed_simulation_only','notifications':2,'duplicate_notifications':0,'notification_links_event_city_time':True,'scientific_cache_unchanged':True}
                shot('G-evento-desde-notificacion')

                timesfm=audit_timesfm();results['H']={'status':'blocked_not_implemented','evidence':timesfm}
                assert not timesfm['enabled'] and timesfm['local_checkpoint_files']==0
                assert not timesfm['installed_dependencies']['torch']

                page.click('#close-inspector');page.locator('#date').fill('2030-01-15T12:00');page.locator('#date').dispatch_event('change')
                wait_frame(day='2030-01-15',kind='climatology_reference')
                assert 'referencia mensual' in page.locator('#map-value').inner_text()
                toggle_tools();page.select_option('#source','gldas');page.click('#close-tools')
                wait_frame(day='2030-01-15',kind='unavailable');assert page.locator('#value').inner_text()=='—'
                results['coverage']={'status':'passed','far_future_reference_identified':True,'gldas_future_not_invented':True}
                toggle_tools();page.select_option('#source','power');page.select_option('#variable','T2M');page.click('#close-tools')
                page.click('#present');wait_frame(day=today.isoformat(),kind='forecast')

                page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(200)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                timeline=page.locator('.timeline').bounding_box();assert timeline['y']>844*.6 and 830<=timeline['y']+timeline['height']<=844
                shot('mobile-mapa');results['mobile']={'status':'passed','timeline_visible':True,'horizontal_overflow':False}
                assert not errors,errors
                browser.close()
        finally:server.shutdown();thread.join(timeout=5)
    after=hashes();changed=[path for path,digest in before.items() if after.get(path)!=digest]
    assert not changed,changed
    report={'status':'complete','finished_at':datetime.now(timezone.utc).isoformat(),'results':results,'javascript_errors':errors,'screenshots':screens,'protected_scientific_files':len(before),
        'changed_scientific_files':changed,'private_database':'temporary_deleted',
        'public_ui_origin':public_url,'private_ui_origin':'http://127.0.0.1:5052',
        'science':'A-F operational/historical values real; only G changes a copy in memory in a temporary DB; H not mocked.'}
    (ROOT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'results':{key:value['status'] for key,value in results.items()},'javascript_errors':errors,'screenshots':screens,'report':str(ROOT/'report.json')},ensure_ascii=True))
    return 0

if __name__=='__main__':raise SystemExit(main())
