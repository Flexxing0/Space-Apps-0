"""Pruebas sin red; observaciones sintéticas sólo para verificar software."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from app import create_app
from services.api_service import ServiceError
from services.providers.cache import utc_now
from services.events.events import validate_event
from services.events.monitoring import MonitoringService
from services.events.planning import evaluate
from services.weather.weather import HOURLY
from tests.providers.test_bulk import synthetic_payload


def synthetic_forecast(event,value=20):
    first=datetime.fromisoformat(event['start']).astimezone(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=7)
    stamps=[(first+timedelta(hours=i)).isoformat() for i in range(24*16)]
    return {'kind':'forecast','provider':'synthetic_software_test_only','product':'not_real_data',
        'fetched_at':utc_now(),'issued_at':None,'uncertainty':None,
        'variables':{code:{'unit':unit,'series':[{'date':d,'value':value} for d in stamps]} for code,unit in HOURLY.items()}}


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.app=create_app({'TESTING':True,'CACHE_DIR':self.root/'cache'/'power','DATABASE_PATH':self.root/'db.sqlite3','SECRET_KEY':'software-tests-only','POWER_REQUEST_DELAY':0})
        self.client=self.app.test_client();self.service=self.app.extensions['earthlens_events']
        start=(datetime.now(timezone(timedelta(hours=-3)))+timedelta(days=3)).replace(hour=10,minute=0,second=0,microsecond=0)
        self.event={'name':'Excursión de prueba sintética','city_id':'comodoro-rivadavia','activity':'excursion',
            'start':start.isoformat(),'end':(start+timedelta(hours=2)).isoformat(),'preferences':{'max_temperature':25,'require_official_alerts':False},'flexible_days':2}
        response=self.client.get('/api/session');self.csrf=response.json['data']['csrf_token']

    def register(self,client=None,name='usuario_prueba'):
        client=client or self.client
        csrf=client.get('/api/session').json['data']['csrf_token']
        response=client.post('/api/session/register',json={'username':name,'password':'synthetic-test-password'},headers={'X-CSRF-Token':csrf})
        self.assertEqual(response.status_code,200,response.json)
        return response.json['data']

    def save(self):
        me=self.register();self.csrf=me['csrf_token']
        r=self.client.post('/api/events',json=self.event,headers={'X-CSRF-Token':self.csrf});self.assertEqual(r.status_code,201,r.json)
        return r.json['data']

    def test_private_endpoints_require_auth(self):
        for path in ['/api/events','/api/events/anything','/api/notifications','/api/events/anything/history']:
            with self.subTest(path=path):self.assertEqual(self.client.get(path).status_code,401)

    def test_csrf_required_for_registration_and_mutations(self):
        self.assertEqual(self.client.post('/api/session/register',json={'username':'test','password':'synthetic-password'}).status_code,403)
        event=self.save();self.assertEqual(self.client.delete('/api/events/'+event['id']).status_code,403)

    def test_event_crud_and_revision(self):
        event=self.save();url='/api/events/'+event['id'];headers={'X-CSRF-Token':self.csrf}
        response=self.client.patch(url,json={'name':'Editado','status':'cancelled'},headers=headers)
        self.assertEqual(response.status_code,200,response.json);self.assertEqual(response.json['data']['revision'],2)
        self.assertEqual(self.client.get(url).json['data']['name'],'Editado')
        self.assertEqual(self.client.delete(url,headers=headers).status_code,200)
        self.assertEqual(self.client.get(url).status_code,404)

    def test_other_account_cannot_read_modify_or_delete(self):
        event=self.save();other=self.app.test_client();me=self.register(other,'otro_usuario');h={'X-CSRF-Token':me['csrf_token']};url='/api/events/'+event['id']
        self.assertEqual(other.get('/api/events').json['data'],[])
        for r in [other.get(url),other.patch(url,json={'name':'intruso'},headers=h),other.delete(url,headers=h),other.get(url+'/history'),other.get(url+'/forecast-history')]:self.assertEqual(r.status_code,404)

    def test_persistence_across_factory_instances(self):
        self.save();app=create_app({'TESTING':True,'DATABASE_PATH':self.root/'db.sqlite3','CACHE_DIR':self.root/'other','SECRET_KEY':'different'})
        with app.extensions['earthlens_store'].connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0],1)
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],1)
            self.assertNotIn('synthetic-test-password',db.execute('SELECT password_hash FROM users').fetchone()[0])

    def test_invalid_events(self):
        data=self.app.extensions['earthlens_service']
        for change in [{'latitude':-45},{'city_id':'paris'},{'participants':True},{'flexible_days':-1},
                {'preferences':{'max_probability':101}},{'preferences':{'max_wind':float('nan')}},
                {'start':'2027-01-01T10:00'},{'outdoor':'yes'},{'preferences':{'min_temperature':30,'max_temperature':20}},
                {'activity':[]},{'transport':{}},{'status':[]}]:
            with self.subTest(change=change),self.assertRaises(ServiceError):validate_event({**self.event,**change},data)

    def test_weather_compatibility_and_unknown_official_alerts(self):
        event=validate_event(self.event,self.app.extensions['earthlens_service']);bundle=synthetic_forecast(event)
        self.assertEqual(evaluate(event,bundle)['status'],'favorable')
        event['preferences']['require_official_alerts']=True
        self.assertEqual(evaluate(event,bundle)['status'],'review')
        self.assertEqual(evaluate(event,synthetic_forecast(event,30))['status'],'unfavorable')

    def test_missing_or_historical_values_never_favorable(self):
        event=validate_event(self.event,self.app.extensions['earthlens_service']);bundle=synthetic_forecast(event)
        bundle['variables']['temperature_2m']['series']=[]
        self.assertEqual(evaluate(event,bundle)['status'],'insufficient')
        self.assertEqual(evaluate(event,failure='timeout')['status'],'insufficient')
        bundle['kind']='reanalysis'
        with self.assertRaises(ValueError):evaluate(event,bundle)

    def test_monitoring_versions_dedup_and_changed_notification(self):
        event=self.save();planning=self.app.extensions['earthlens_planning'];monitor=MonitoringService(self.service,planning)
        bundle=synthetic_forecast(event)
        with patch.object(planning.weather,'bundle',return_value=bundle):
            first=monitor.run(force=True);second=monitor.run(force=True)
            self.assertEqual(first['summary']['notifications'],1,first)
            self.assertEqual(second['summary']['notifications'],0,second)
            self.assertEqual(second['summary']['unchanged'],1,second)
        with patch.object(planning.weather,'bundle',return_value=synthetic_forecast(event,30)):
            third=monitor.run(force=True);self.assertEqual(third['summary']['notifications'],1,third)
        self.assertEqual(len(self.client.get('/api/notifications').json['data']),2)
        changes=self.client.get('/api/notifications').json['data'][0]['body']
        self.assertEqual(changes['event']['city_id'],'comodoro-rivadavia')
        self.assertTrue(any(row['previous_value']==20 and row['current_value']==30 for row in changes['changes']))
        history=self.client.get('/api/events/'+event['id']+'/history').json['data'];self.assertEqual(len(history),2)
        self.assertEqual({r['assessment']['status'] for r in history},{'favorable','unfavorable'})
        versions=self.client.get('/api/events/'+event['id']+'/forecast-history').json['data']
        self.assertEqual(len(versions['versions']),2);self.assertEqual([r['value'] for r in versions['versions']],[20,30])

    def test_monitoring_failure_and_cancelled_event(self):
        event=self.save();planning=self.app.extensions['earthlens_planning'];monitor=MonitoringService(self.service,planning)
        with patch.object(planning.weather,'bundle',side_effect=ServiceError('provider_timeout','simulación de prueba')):
            result=monitor.run(force=True);self.assertEqual(result['summary']['failed'],1)
            self.assertEqual(self.service.history(self.client.get('/api/session').json['data']['user']['id'],event['id'])[0]['assessment']['status'],'insufficient')
        self.client.patch('/api/events/'+event['id'],json={'status':'cancelled'},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(monitor.run(force=True)['summary']['examined'],0)

    def test_preview_alternatives_keep_duration_and_require_explicit_save(self):
        event=self.save();planning=self.app.extensions['earthlens_planning']
        with patch.object(planning.weather,'bundle',return_value=synthetic_forecast(event)):
            r=self.client.post('/api/events/preview',json=self.event,headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(r.status_code,200,r.json);self.assertEqual(len(r.json['data']['alternatives']),4)
        self.assertNotIn('bundle',r.json['data']);self.assertEqual(self.client.get('/api/events').json['data'][0]['start'],event['start'])
        with patch.object(planning.weather,'bundle',return_value=synthetic_forecast(event)):
            changed=self.client.post('/api/events/preview',json={**self.event,'flexible_days':0,'flexible_hours':2},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(len(changed.json['data']['alternatives']),4)
        self.assertEqual({a['offset_hours'] for a in changed.json['data']['alternatives']},{-2,-1,1,2})

    def test_unknown_inputs_and_geography(self):
        for url in ['/api/weather','/api/weather?city_id=paris','/api/workspace/series','/api/workspace/series?city_id=mendoza&latitude=0']:
            self.assertIn(self.client.get(url).status_code,[400,404])

    def test_real_incident_reference_and_impact_limitations(self):
        rows=self.client.get('/api/workspace/incidents?city_id=comodoro-rivadavia').json['data']
        self.assertEqual(rows[0]['start'],'2017-03-29');self.assertTrue(rows[0]['sources'])
        self.assertEqual(self.client.get('/api/workspace/incidents?city_id=mendoza').json['data'],[])
        impact=self.client.get('/api/impact?city_id=comodoro-rivadavia').json['data']
        self.assertFalse(impact['hazard_map_enabled']);self.assertEqual(impact['geometries'],[])

    def test_historical_reads_use_cache_and_preserve_monthly_units(self):
        def respond(url,*,params,timeout):
            r=Mock();r.json.return_value=synthetic_payload(params);return r
        with patch('services.providers.power.requests.get',side_effect=respond):
            self.app.extensions['earthlens_service'].get_data({'city_id':'mendoza','start_year':2000,'end_year':2024})
        with patch('requests.sessions.Session.request',side_effect=AssertionError('network forbidden')):
            r=self.client.get('/api/workspace/series?city_id=mendoza&variable=PRECTOTCORR&start=2017-03-01&end=2017-04-30')
            self.assertEqual(r.status_code,200,r.json);self.assertEqual(len(r.json['data']['series']),2);self.assertEqual(r.json['data']['unit'],'mm/day')
            profile=self.client.get('/api/workspace/profiles/mendoza');self.assertEqual(profile.status_code,200,profile.json)
            self.assertEqual(profile.json['data']['climatology']['T2M']['months'][0]['count'],25)
            report=self.client.get('/api/workspace/report.pdf?city_id=mendoza&variable=T2M&start=2000-01-01&end=2024-12-31')
            self.assertEqual(report.status_code,200,report.data[:100]);self.assertTrue(report.data.startswith(b'%PDF-'))
            day=self.client.get('/api/workspace/series?city_id=mendoza&variable=T2M&start=2017-03-29&end=2017-03-29')
            self.assertEqual(len(day.json['data']['series']),1);self.assertEqual(day.json['data']['frequency'],'monthly')

    def test_new_pages_and_legacy_remain_accessible(self):
        for url in ['/time-machine','/time-machine/legacy','/cities','/cities/mendoza','/laboratory','/my-space']:
            self.assertEqual(self.client.get(url).status_code,200,url)

    def test_private_pdf_requires_owner_and_contains_pdf(self):
        event=self.save();response=self.client.get('/api/events/'+event['id']+'/report.pdf')
        self.assertEqual(response.status_code,200,response.data[:100]);self.assertTrue(response.data.startswith(b'%PDF-'))
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        other=self.app.test_client();self.register(other,'report_other_user')
        self.assertEqual(other.get('/api/events/'+event['id']+'/report.pdf').status_code,404)

    def test_monitoring_lease_prevents_concurrent_run(self):
        monitor=MonitoringService(self.service,self.app.extensions['earthlens_planning'])
        with self.service.store.connect() as db:
            db.execute('INSERT INTO monitoring_leases VALUES(?,?,?)',('events','another-worker',(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()))
        self.assertEqual(monitor.run()['status'],'already_running')

    def test_login_failed_attempts_committed_and_rate_limited(self):
        self.register();csrf=self.client.get('/api/session').json['data']['csrf_token']
        for i in range(10):
            r=self.client.post('/api/session/login',json={'username':'usuario_prueba','password':'wrong-software-password'},headers={'X-CSRF-Token':csrf})
            self.assertEqual(r.status_code,401)
        r=self.client.post('/api/session/login',json={'username':'usuario_prueba','password':'wrong-software-password'},headers={'X-CSRF-Token':csrf})
        self.assertEqual(r.status_code,429)

    def test_climatology_does_not_generate_future_daily_forecast(self):
        workspace=self.app.extensions['earthlens_workspace']
        fake={'reference_period':{'start_year':2000,'end_year':2024},'method':'synthetic_software_test',
            'climatology':{'T2M':{'unit':'C','months':[{'mean':10,'month':i,'count':25} for i in range(1,13)]}}}
        with patch.object(workspace,'profile',return_value=fake):
            r=self.client.get('/api/workspace/climatology?city_id=mendoza&date=2030-01-15')
        self.assertEqual(r.status_code,200);self.assertEqual(r.json['data']['kind'],'climatology_reference')
        self.assertNotIn('series',r.json['data'])
        r=self.client.get('/api/workspace/series?city_id=mendoza&start=2027-01-01&end=2027-01-31')
        self.assertEqual(r.status_code,503)


class BacktestingTests(unittest.TestCase):
    def test_backtest_avoids_future_leakage_and_uses_daily_only(self):
        from services.prediction.prediction import backtest_daily
        points=[{'date':(datetime(2024,1,1)+timedelta(days=i)).date().isoformat(),'value':float(i)} for i in range(40)]
        lengths=[]
        def predictor(train,horizon):
            lengths.append((len(train),max(train)))
            return {'point':[train[-1]]*horizon,'lower':[train[-1]-5]*horizon,'upper':[train[-1]+5]*horizon}
        result=backtest_daily(points,[14,21,28],(1,3,7),predictor)
        self.assertEqual(lengths,[(14,13),(21,20),(28,27)]);self.assertEqual(len(result['rows']),27)
        self.assertTrue(all(r['mae']>=0 and r['rmse']>=0 for r in result['rows']))
        points[1]['date']='2024-02-01'
        with self.assertRaises(ValueError):backtest_daily(points,[14])

    def test_timesfm_is_not_claimed_available_or_validated(self):
        from services.prediction.prediction import capabilities
        row=capabilities();self.assertFalse(row['enabled']);self.assertFalse(row['recommended_dates_enabled'])


class CityContextTests(unittest.TestCase):
    def test_elevation_is_cached_with_point_units_and_invalid_refresh_preserves_it(self):
        from scripts.data import fetch_city_context as context
        from services.geography.cities import get_city
        with tempfile.TemporaryDirectory() as temp,patch.object(context,'ROOT',Path(temp)):
            response=Mock();response.json.return_value={'elevation':[123.0]}
            with patch.object(context.requests,'get',return_value=response) as network:
                row=context.elevations([get_city('mendoza')]);context.elevations([get_city('mendoza')])
                self.assertEqual(network.call_count,1);self.assertEqual(row['unit'],'m')
            original=(Path(temp)/'elevation.json').read_bytes()
            response.json.return_value={'elevation':[None]}
            with patch.object(context.requests,'get',return_value=response),self.assertRaises(ValueError):context.elevations([get_city('mendoza')],force=True)
            self.assertEqual((Path(temp)/'elevation.json').read_bytes(),original)

    def test_only_geolocated_attributed_compatible_images_are_cached(self):
        from scripts.data import fetch_city_context as context
        from services.geography.cities import get_city
        page={'title':'File:Mendoza software test.jpg','coordinates':[{'lat':-32.9,'lon':-68.85}],
            'imageinfo':[{'thumburl':'https://upload.wikimedia.org/test-only.jpg','descriptionurl':'https://commons.wikimedia.org/wiki/File:Test',
                'extmetadata':{'LicenseShortName':{'value':'CC BY-SA 4.0'},'Artist':{'value':'<b>Software Test Author</b>'},
                    'ImageDescription':{'value':'Mendoza, software test only'}}}]}
        with tempfile.TemporaryDirectory() as temp,patch.object(context,'ROOT',Path(temp)):
            response=Mock();response.json.return_value={'query':{'pages':{'1':page}}}
            with patch.object(context.requests,'get',return_value=response):
                result=context.photo(get_city('mendoza'))
                self.assertEqual(result['status'],'available');self.assertEqual(result['author'],'Software Test Author')
                page['imageinfo'][0]['extmetadata']['LicenseShortName']['value']='All rights reserved'
                result=context.photo(get_city('mendoza'),force=True);self.assertEqual(result['status'],'no_verified_licensed_photo')


class WeatherContractTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.app=create_app({'TESTING':True,'CACHE_DIR':Path(tmp.name)/'cache'/'power'})
        self.weather=self.app.extensions['earthlens_weather']
        today=datetime.now(timezone.utc).date();self.start=today.isoformat();self.end=(today+timedelta(days=1)).isoformat()

    def test_hourly_normalization_cache_and_failed_refresh_preserved(self):
        today=datetime.now(timezone.utc).date();times=[datetime.combine(today,datetime.min.time())+timedelta(hours=i) for i in range(16*24)]
        raw={'hourly':{'time':[d.isoformat(timespec='minutes') for d in times],**{v:[1.0]*len(times) for v in HOURLY}},'hourly_units':HOURLY.copy(),'latitude':-45.9,'longitude':-67.5}
        response=Mock();response.json.return_value=raw
        with patch.object(self.weather.session,'get',return_value=response) as network:
            one=self.weather.series('mendoza','forecast','temperature_2m',self.start,self.end)
            self.assertEqual(len(one['series']),48);self.assertIsNone(one['issued_at'])
            self.weather.series('mendoza','forecast','wind_speed_10m',self.start,self.end);self.assertEqual(network.call_count,1)
        hashes={p:p.read_bytes() for p in self.weather.cache.directory.glob('*.json')}
        raw['hourly']['temperature_2m'][0]=None
        with patch.object(self.weather.session,'get',return_value=response),self.assertRaises(ServiceError):self.weather.bundle('mendoza',force=True)
        self.assertTrue(all(p.read_bytes()==b for p,b in hashes.items()))

    def test_invalid_dates_horizons_and_units(self):
        with self.assertRaises(ServiceError):self.weather.bundle('mendoza',start='2040-01-01',end='2040-01-02')
        with self.assertRaises(ServiceError):self.weather.series('mendoza',variable='not_a_variable')
        with self.assertRaises(ServiceError):self.weather.bundle('mendoza',start='2024-01-01',end='2020-01-01')

    def test_commercial_access_requires_key(self):
        with patch.dict('os.environ',{},clear=True):
            self.weather.commercial=True
            with self.assertRaises(ServiceError) as error:self.weather.bundle('mendoza')
            self.assertEqual(error.exception.code,'provider_auth_required')
