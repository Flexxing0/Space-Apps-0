"""Chrome optativo con cachés reales: Time Machine integrado, sin respaldo sintético."""

import hashlib
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def protected():
    files=list(Path('data/cache/power').glob('*.json'))+[Path('data/cache/radar/latest.json')]
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def main():
    before=protected();errors=[];calls=[];checks=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda r:calls.append(r.post_data_json) if '/api/time-machine' in r.url else None)
        page.goto('http://127.0.0.1:5000/time-machine/legacy',wait_until='networkidle')
        page.wait_for_function("document.querySelectorAll('#tmTimelineTableBody tr').length===25")
        assert page.locator('#tmDataNotice').get_attribute('data-error')=='false'
        assert page.locator('#btnShrinkBox').is_disabled()
        assert page.evaluate("['tmTrendChart','tmAnomalyBarChart'].every(id=>Chart.getChart(document.getElementById(id)))")
        checks.append('25 años reales; dos gráficos; sin cuadrantes simulados')
        count=len(calls)
        page.locator('#tmYearSlider').fill('2010')
        assert page.locator('#tmActiveYearDisplay').inner_text()=='2010'
        assert len(calls)==count
        checks.append('Deslizador histórico sin consultas adicionales')
        page.select_option('#tmCitySelect','mendoza')
        page.wait_for_function("document.querySelectorAll('#tmTimelineTableBody tr').length===25 && document.querySelector('#tmRegionBadge').textContent==='Cuyo' && document.querySelector('#tmDataNotice').dataset.error==='false'")
        assert calls[-1]['city_id']=='mendoza'
        checks.append('Cambio de ciudad mediante ID argentino')
        page.screenshot(path='data/cache/reports/time-machine-merge-desktop.png',full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        page.wait_for_timeout(350)
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
        page.screenshot(path='data/cache/reports/time-machine-merge-mobile.png',full_page=True)
        checks.append('Vista móvil sin desborde horizontal')
        # Error de software interceptado sólo en esta prueba, nunca datos de producción.
        page.route('**/api/time-machine',lambda route:route.fulfill(status=503,content_type='application/json',body=json.dumps({'status':'error','error':{'message':'Proveedor de prueba no disponible'}})))
        if not page.locator('#tmCitySelect').is_visible():page.click('#btnToggleTopFilters')
        page.select_option('#tmCitySelect','posadas')
        page.wait_for_function("document.querySelector('#tmDataNotice').dataset.error==='true'")
        assert page.locator('#tmTimelineTableBody tr').count()==0
        assert page.locator('#tmActiveValue').inner_text()=='--'
        checks.append('HTTP 503 limpia los resultados y no genera un respaldo')
        browser.close()
    assert not errors,errors
    assert before==protected()
    print(json.dumps({'status':'ok','checks':checks,'javascript_errors':errors,'original_cache_hashes_preserved':True},ensure_ascii=True))


if __name__=='__main__':main()
