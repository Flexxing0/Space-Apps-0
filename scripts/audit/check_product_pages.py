"""Prueba optativa de navegador de Radar/Fingerprint con Docker y la caché real.

Requiere Playwright y Chrome en el host; no agrega dependencias al contenedor.
Los errores, metadatos incompatibles e indicador adicional interceptados son
pruebas de software explícitas y nunca se guardan como resultados científicos.
Las capturas se toman exclusivamente con respuestas reales.
"""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright


def protected_hashes():
    paths = list(Path("data/cache/power").glob("*.json"))
    paths += [Path("data/cache/radar/latest.json"), Path("services/science/trend_analysis.py")]
    assert len(paths) == 27, "Esta verificación requiere las 25 cachés reales y el estudio original."
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:5000")
    parser.add_argument("--browser", default="C:/Program Files/Google/Chrome/Application/chrome.exe")
    args = parser.parse_args()
    root = args.url.rstrip("/")
    reports = Path("data/cache/reports/interfaces-phase1") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    reports.mkdir(parents=True, exist_ok=False)
    before = protected_hashes()
    checks, errors, origins = [], [], []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.browser, headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        # Ignorar AbortController aquí fuerza también la defensa por secuencia.
        # Las respuestas tardías reales se entregan después de la selección nueva.
        context.add_init_script("""const originalFetch = window.fetch;
          window.fetch = (url, options = {}) => { const {signal, ...rest} = options;
            return originalFetch(url, rest); };""")
        page = context.new_page()
        page.set_default_timeout(20000)
        page.on("pageerror", lambda error: errors.append(str(error)))

        def api(path):
            response = context.request.get(root + path)
            assert response.ok, (path, response.status)
            return response.json()["data"]

        def radar_ready(count):
            page.wait_for_function("n => document.querySelector('#radar-status')?.classList.contains('is-success') && document.querySelectorAll('.result-card').length === n", arg=count)
            assert page.locator("#radar-test-count").inner_text() == "150"
            assert page.locator(".leaflet-interactive").count() == 25

        def fingerprint_ready(title, datasets=1):
            page.wait_for_function("name => document.querySelector('#fingerprint-output') && !document.querySelector('#fingerprint-output').hidden && document.querySelector('#fingerprint-title').textContent === name", arg=title)
            assert page.locator(".fingerprint-card").count() == 6
            assert page.locator("canvas").count() == 6
            assert page.evaluate("Array.from(document.querySelectorAll('canvas')).every(canvas => Chart.getChart(canvas).data.datasets.length === " + str(datasets) + ")")

        def capture(name):
            page.screenshot(path=str(reports / f"{name}.png"), full_page=True)

        def wait_held(held):
            for _ in range(200):
                if "response" in held:
                    return
                page.wait_for_timeout(100)
            raise AssertionError("La respuesta retenida no llegó")

        study = api("/api/radar")
        assert study["summary"]["tests"] == 150 and len(study["cities"]) == 25
        for city in study["cities"]:
            profile = api("/api/fingerprint/" + city["id"])
            assert len(profile["results"]) == 6
            assert all(row["provenance"]["origin"] == "cache" for row in profile["results"])
            origins.append({"city_id": city["id"], "origin": "cache", "variables": 6})
        checks.append("25 perfiles reales: seis variables por ciudad y origen cache")

        page.goto(root + "/radar", wait_until="networkidle")
        radar_ready(25)
        assert page.locator("#radar-signal-count").inner_text() == "48"
        assert "provisional" in page.locator(".product-notice").inner_text()
        page.locator(".leaflet-interactive").first.click(force=True)
        page.wait_for_selector(".radar-city-popup")
        assert page.locator(".radar-city-popup a").count() >= 2
        page.locator(".leaflet-popup-close-button").click()
        page.select_option("#radar-sort", "p_value")
        expected = sorted(api("/api/radar?variable=T2M")["results"], key=lambda row: (row["statistics"]["p_value"], row["location"]["name"]))
        assert page.locator(".result-card").first.get_attribute("data-city-id") == expected[0]["location"]["id"]
        capture("radar-desktop")
        for selector, value, query in [
            ("#radar-province", "Chubut", "province=Chubut&variable=T2M"),
            ("#radar-region", "Cuyo", "region=Cuyo&variable=T2M"),
            ("#radar-variable", "PRECTOTCORR", "variable=PRECTOTCORR"),
            ("#radar-direction", "decreasing", "variable=T2M&direction=decreasing"),
            ("#radar-evidence", "provisional_signal", "variable=T2M&evidence_status=provisional_signal")
        ]:
            page.click("#radar-reset")
            radar_ready(25)
            page.select_option(selector, value)
            radar_ready(api("/api/radar?" + query)["view"]["count"])
        page.click("#radar-reset")
        radar_ready(25)
        page.select_option("#radar-variable", "")
        radar_ready(150)
        assert page.locator('#radar-sort option[value="change_desc"]').is_disabled()
        page.reload(wait_until="networkidle")
        radar_ready(150)  # Enlace compartido conserva «todos los indicadores».
        page.select_option("#radar-evidence", "confirmed")
        radar_ready(0)
        assert page.locator("#radar-empty").is_visible()
        page.click("#radar-empty-reset")
        radar_ready(25)
        checks.append("Radar: cinco filtros, orden, familia global, 25 marcadores y vacío real")

        held = {}
        def hold_radar(route):
            if parse_qs(urlparse(route.request.url).query).get("region") == ["Cuyo"]:
                held["route"] = route
                held["response"] = route.fetch()
            else:
                route.continue_()
        page.route("**/api/radar?*", hold_radar)
        page.select_option("#radar-region", "Cuyo")
        wait_held(held)
        page.select_option("#radar-region", "NEA")
        nea_count = api("/api/radar?variable=T2M&region=NEA")["view"]["count"]
        radar_ready(nea_count)
        held["route"].fulfill(response=held["response"])
        page.wait_for_timeout(250)
        radar_ready(nea_count)
        assert all("NEA" in text for text in page.locator(".result-card-header").all_inner_texts())
        page.unroute("**/api/radar?*", hold_radar)
        checks.append("Radar: respuesta anterior fuera de orden ignorada aun sin cancelación")

        failure = json.dumps({"status": "error", "error": {"message": "Error simulado de software; no dato científico"}})
        page.route("**/api/radar?*", lambda route: route.fulfill(status=503, content_type="application/json", body=failure))
        page.click("#radar-reset")
        page.wait_for_selector("#radar-status.is-error")
        assert page.locator(".result-card").count() == 0 and page.locator("#radar-empty").is_hidden()
        page.select_option("#radar-sort", "city")
        assert page.locator(".result-card").count() == 0
        page.unroute("**/api/radar?*")
        page.click("#radar-retry")
        radar_ready(25)
        with page.expect_navigation():
            page.locator('.result-card[data-city-id="mendoza"] a.btn-primary').click()
        page.wait_for_function("document.querySelectorAll('#seriesTableBody tr').length === 25")
        assert page.locator("#resLocationTitle").inner_text() == "Mendoza"
        checks.append("Radar: error sin datos anteriores, reintento y enlace a Resultados real")

        page.goto(root + "/fingerprint", wait_until="networkidle")
        fingerprint_ready("Comodoro Rivadavia")
        assert page.locator("#fingerprint-city option").count() == 25
        real = api("/api/fingerprint/comodoro-rivadavia")["results"]
        first_chart = page.evaluate("Chart.getChart(document.querySelector('canvas')).data.datasets[0].data")
        assert first_chart == [point["value"] for point in real[0]["series"]]
        for city, name in [("mendoza", "Mendoza"), ("posadas", "Posadas"), ("comodoro-rivadavia", "Comodoro Rivadavia")]:
            page.select_option("#fingerprint-city", city)
            fingerprint_ready(name)
        capture("fingerprint-desktop")
        page.select_option("#fingerprint-compare-city", "mendoza")
        fingerprint_ready("Comodoro Rivadavia y Mendoza", 2)
        assert "compatibles" in page.locator("#fingerprint-comparison-status").inner_text()
        assert page.locator('.fingerprint-card a[href^="/compare?"]').count() == 6
        capture("fingerprint-comparison-desktop")
        checks.append("Fingerprint: Comodoro/Mendoza/Posadas, series idénticas a API y comparación compatible")

        page.select_option("#fingerprint-compare-city", "")
        fingerprint_ready("Comodoro Rivadavia")
        held = {}
        def hold_mendoza(route):
            held["route"] = route
            held["response"] = route.fetch()
        page.route("**/api/fingerprint/mendoza", hold_mendoza)
        page.select_option("#fingerprint-city", "mendoza")
        wait_held(held)
        assert page.locator("#fingerprint-output").is_hidden()
        page.select_option("#fingerprint-city", "posadas")
        fingerprint_ready("Posadas")
        held["route"].fulfill(response=held["response"])
        page.wait_for_timeout(250)
        fingerprint_ready("Posadas")
        assert page.evaluate("Chart.getChart(document.querySelector('canvas')).data.datasets[0].label") == "Posadas"
        page.unroute("**/api/fingerprint/mendoza", hold_mendoza)
        # El mismo control de secuencia se prueba para la segunda ciudad.
        held = {}
        page.route("**/api/fingerprint/mendoza", hold_mendoza)
        page.select_option("#fingerprint-compare-city", "mendoza")
        wait_held(held)
        page.select_option("#fingerprint-compare-city", "ushuaia")
        fingerprint_ready("Posadas y Ushuaia", 2)
        held["route"].fulfill(response=held["response"])
        page.wait_for_timeout(250)
        fingerprint_ready("Posadas y Ushuaia", 2)
        assert page.evaluate("Chart.getChart(document.querySelector('canvas')).data.datasets[1].label") == "Ushuaia"
        page.unroute("**/api/fingerprint/mendoza", hold_mendoza)
        checks.append("Fingerprint: selecciones rápidas de ambas ciudades conservan título, datos y gráficos actuales")

        page.route("**/api/fingerprint/*", lambda route: route.fulfill(status=503, content_type="application/json", body=failure))
        page.select_option("#fingerprint-compare-city", "")
        page.wait_for_selector("#fingerprint-status.is-error")
        assert page.locator("#fingerprint-output").is_hidden() and page.locator("canvas").count() == 0
        page.unroute("**/api/fingerprint/*")
        page.click("#fingerprint-retry")
        fingerprint_ready("Posadas")
        page.select_option("#fingerprint-compare-city", "posadas")
        page.wait_for_selector("#fingerprint-status.is-error")
        assert "distintas" in page.locator("#fingerprint-status").inner_text()
        page.select_option("#fingerprint-compare-city", "")
        fingerprint_ready("Posadas")

        # Sólo metadatos de compatibilidad alterados: valores siguen reales.
        def incompatible(route):
            response = route.fetch()
            body = response.json()
            body["data"]["comparison"]["key"] = "contrato-incompatible-de-prueba-software"
            route.fulfill(response=response, json=body)
        page.route("**/api/fingerprint/mendoza", incompatible)
        page.select_option("#fingerprint-compare-city", "mendoza")
        page.wait_for_function("document.querySelectorAll('canvas').length === 12")
        assert "no cumplen" in page.locator("#fingerprint-comparison-status").inner_text()
        assert page.locator('.fingerprint-card a[href^="/compare?"]').count() == 0
        page.unroute("**/api/fingerprint/mendoza", incompatible)

        # Fixture de software claramente rotulado: prueba extensibilidad y faltantes.
        def dynamic_contract(route):
            response = route.fetch()
            body = response.json()
            row = deepcopy(body["data"]["results"][0])
            row.update(variable="UI_TEST_ONLY", statistics=None, series=[], direction=None,
                       data_status="insufficient", status="insufficient")
            row["indicator"] = {"id": "software_test_only", "name": "Contrato sintético de prueba de interfaz — no dato científico", "group": "additional"}
            row["evidence"]["status"] = "insufficient_data"
            row["coverage"] = {"monthly": {"expected_count": 300, "valid_count": 0},
                               "annual": {"valid_years": 0, "requested_years": 25, "coverage_ratio": 0}}
            body["data"]["results"].append(row)
            body["data"]["summary"]["variables"] = 7
            route.fulfill(response=response, json=body)
        page.route("**/api/fingerprint/posadas", dynamic_contract)
        page.select_option("#fingerprint-compare-city", "")
        page.wait_for_function("document.querySelectorAll('.fingerprint-card').length === 7")
        fixture = page.locator('.fingerprint-card[data-variable="UI_TEST_ONLY"]')
        assert "Cobertura insuficiente" in fixture.inner_text()
        assert fixture.locator("dd").first.inner_text().startswith("—")
        assert fixture.locator("canvas").count() == 0
        page.unroute("**/api/fingerprint/posadas", dynamic_contract)
        checks.append("Fingerprint: errores/reintento, ciudades distintas, incompatibilidad sin superposición e indicador dinámico insuficiente")

        # Todas las capturas siguientes vuelven a usar respuestas reales.
        for width in [1280, 820, 390]:
            page.set_viewport_size({"width": width, "height": 900})
            for product in ["radar", "fingerprint"]:
                page.goto(root + "/" + product, wait_until="networkidle")
                radar_ready(25) if product == "radar" else fingerprint_ready("Comodoro Rivadavia")
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (width, product)
                assert page.locator(".navbar-toggler").is_visible()
                page.locator(".navbar-toggler").click()
                page.wait_for_selector("#earthlensNavbar.show")
                assert page.locator('nav a[href="/radar"]').is_visible()
                assert page.locator('nav a[href="/fingerprint"]').is_visible()
                page.locator(".navbar-toggler").click()
                page.wait_for_timeout(400)
                capture(f"{product}-{width}px")
        # Navegación móvil real entre ambos productos.
        page.locator(".navbar-toggler").click()
        page.locator('nav a[href="/radar"]').click()
        radar_ready(25)
        page.locator(".navbar-toggler").click()
        page.locator('nav a[href="/fingerprint"]').click()
        fingerprint_ready("Comodoro Rivadavia")
        page.locator('.fingerprint-card[data-variable="PRECTOTCORR"] a').first.click()
        page.wait_for_function("document.querySelector('#select-city')?.value === 'comodoro-rivadavia'")
        assert page.locator("#select-variable").input_value() == "PRECTOTCORR"
        checks.append("Responsive 1440/1280/820/390, navegación móvil y enlace a Explorador")
        page.goto(root + "/fingerprint?city_id=mendoza&city_id_b=posadas", wait_until="networkidle")
        fingerprint_ready("Mendoza y Posadas", 2)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        capture("fingerprint-comparison-mobile")
        # Otro contexto mantiene AbortController real (los anteriores fuerzan secuencia).
        native = browser.new_context(viewport={"width": 1440, "height": 1000})
        native_page = native.new_page()
        native_page.on("pageerror", lambda error: errors.append(str(error)))
        native_page.goto(root + "/fingerprint", wait_until="networkidle")
        native_page.wait_for_selector("#fingerprint-output:not([hidden])")
        native_page.evaluate("""() => { const select = document.querySelector('#fingerprint-city');
          for (const id of ['mendoza', 'comodoro-rivadavia', 'posadas']) {
            select.value = id; select.dispatchEvent(new Event('change', {bubbles: true})); } }""")
        native_page.wait_for_function("document.querySelector('#fingerprint-title').textContent === 'Posadas' && !document.querySelector('#fingerprint-output').hidden")
        assert native_page.evaluate("Chart.getChart(document.querySelector('canvas')).data.datasets[0].label") == "Posadas"
        native_page.goto(root, wait_until="networkidle")
        native_page.select_option("#home-city-select", "mendoza")
        native_page.wait_for_function("document.querySelector('#data-source-status').textContent.includes('caché')")
        assert native_page.locator("nav .js-go-explorer-link").get_attribute("href") == "/explorer?city_id=mendoza"
        native.close()
        checks.append("Comparación móvil, cancelación nativa y selección de Inicio conservada al ir a Explorador")
        assert not errors, errors
        browser.close()

    assert protected_hashes() == before, "Se modificó caché científica, estudio o motor"
    report = {"status": "ok", "checks": checks, "javascript_errors": errors,
              "study_summary": study["summary"], "profiles": origins,
              "protected_sha256": before, "scientific_data_modified": False,
              "software_fixtures": "503, metadatos incompatibles e indicador insuficiente sólo interceptados en Chrome; sin persistencia científica"}
    (reports / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "checks": len(checks), "javascript_errors": errors, "reports": str(reports)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
