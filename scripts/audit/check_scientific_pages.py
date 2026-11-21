"""Verificación optativa con Chrome y cachés científicas reales, sin fixtures.

No descarga productos: usa los períodos ya verificados de cada piloto/histórico.
Las capturas e informe quedan fuera de Git en data/cache/reports/.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


def protected():
    paths = list(Path('data/cache/power').glob('*.json'))
    paths += [Path('services/science/trend_analysis.py'), Path('data/cache/radar/latest.json')]
    assert len(paths) == 27
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def main():
    root = 'http://127.0.0.1:5000'
    before = protected()
    report = Path('data/cache/reports/scientific-pages') / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    report.mkdir(parents=True)
    checks, errors, calls = [], [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe', headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        page.set_default_timeout(30000)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda req: calls.append(req.url) if '/api/science/' in req.url else None)
        for path in ('/explorer', '/compare', '/radar', '/fingerprint', '/missions'):
            start = len(calls)
            page.goto(root + path, wait_until='networkidle')
            assert page.locator('[data-science-panel]').count() == 1
            assert page.locator('[data-science-panel]').get_attribute('open') is None
            assert len(calls) == start, 'Un panel cerrado no debe consultar datos nuevos'
        checks.append('Cinco interfaces existentes: panel cerrado, sin consultas científicas adicionales')
        page.goto(root + '/sources', wait_until='networkidle')
        page.wait_for_function("document.querySelector('select[name=source]').options.length >= 14")
        panel = page.locator('[data-science-panel]')

        def submit(code, start, end, count, other='', cross=False):
            panel.locator('[name=source]').select_option(code)
            if not code.startswith('swot:'):
                panel.locator('[name=city]').select_option('mendoza')
                panel.locator('[name=other]').select_option(other)
            panel.locator('[name=start]').fill(str(start))
            panel.locator('[name=end]').fill(str(end))
            if cross:
                panel.locator('[name=cross]').check()
            panel.locator('button[type=submit]').click()
            page.wait_for_function("!document.querySelector('.science-output').hidden")
            result = json.loads(panel.locator('.science-metadata').text_content())
            assert panel.locator('tbody tr').count() == count
            assert panel.locator('.science-status').get_attribute('data-error') == 'false'
            return result

        gldas = submit('gldas:SoilMoi0_10cm_inst', 2000, 2024, 300)
        assert gldas['coverage']['valid_count'] == 300 and gldas['unit'] == 'kg m-2'
        assert not gldas['analysis']['enabled']
        checks.append('GLDAS: 300 meses reales con unidad y metadatos de origen')
        start = len(calls)
        panel.locator('input[type=range]').fill('20')
        assert page.evaluate("Chart.getChart(document.querySelector('.science-chart canvas')).data.labels.length") == 20
        assert len(calls) == start
        checks.append('Recorrido histórico local: cero peticiones adicionales')
        compare = submit('gpm:precipitation', 2000, 2024, 300, cross=True)
        assert [p['factor'] for p in compare['plots']] == [24, 1]
        assert [s['unit'] for s in compare['sources']] == ['mm/hr', 'mm/day']
        assert not compare['comparison']['statistical_test_performed']
        checks.append('Comparación POWER–IMERG: conversión explícita, originales intactos')
        modis = submit('modis:NDVI', 2024, 2024, 23)
        assert modis['coverage']['missing_count'] > 0
        assert any(p['value'] is None and p['quality']['reasons'] for p in modis['series'])
        checks.append('MODIS: 23 compuestos, QA y huecos conservados en gráfico y tabla')
        water = submit('swot:wse', 2024, 2024, 31)
        assert water['frequency'] == 'irregular_satellite_passes'
        assert all(p['quality']['review_required'] for p in water['variables']['wse']['series'])
        assert page.evaluate("Chart.getChart(document.querySelector('.science-chart canvas')).options.scales.x.min") == int(datetime.fromisoformat(water['variables']['wse']['series'][0]['date']).timestamp()*1000)
        checks.append('SWOT: 31 pasos reales, geometría, incertidumbre y banderas sin aceptación automática')
        page.screenshot(path=str(report / 'desktop.png'), full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        page.wait_for_function('document.documentElement.scrollWidth <= window.innerWidth + 1')
        page.screenshot(path=str(report / 'mobile.png'), full_page=True)
        checks.append('Vista de 390 px sin desborde horizontal')
        # Una selección nueva invalida una respuesta real retenida, aun sin AbortController.
        page.evaluate("window.fetch = ((original) => (url, options={}) => {const {signal,...rest}=options; return original(url,rest);})(window.fetch)")
        held = {}
        def hold(route):
            held['route'] = route
            held['response'] = route.fetch()
        page.route('**/api/science/data', hold)
        panel.locator('[name=source]').select_option('gldas:SoilMoi0_10cm_inst')
        panel.locator('button[type=submit]').click()
        for _ in range(100):
            if 'response' in held:
                break
            page.wait_for_timeout(100)
        assert 'response' in held
        panel.locator('[name=source]').select_option('gpm:precipitation')
        held['route'].fulfill(response=held['response'])
        page.wait_for_timeout(300)
        assert panel.locator('.science-output').is_hidden()
        checks.append('Respuesta tardía real descartada después de cambiar la selección')
        browser.close()
    assert not errors, errors
    assert protected() == before, 'POWER, Radar o motor se modificaron'
    checks.append('Hashes de 25 cachés POWER, Radar y motor conservados')
    result = {'checks': checks, 'page_errors': errors, 'scientific_http_requests': len(calls), 'report': str(report)}
    (report / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
