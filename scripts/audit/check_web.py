"""Verificación optativa en Chrome/Edge real. Requiere playwright en el host.

Usa sólo el período ya cacheado 2000–2024. No fuerza actualizaciones NASA.
La respuesta 503 interceptada comprueba errores de software y no es un dato científico.
"""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:5000")
    parser.add_argument("--browser", default="C:/Program Files/Google/Chrome/Application/chrome.exe")
    args = parser.parse_args()
    reports = Path("data/cache/reports/web")
    reports.mkdir(parents=True, exist_ok=True)
    errors, responses = [], []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.browser, headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))

        def record(response):
            if "/api/" in response.url and response.ok:
                body = response.json()
                if response.url.endswith("/analyze"):
                    assert body["data"]["is_mock"] is False
                    assert body["meta"]["origin"] == "cache"
                    assert len(body["data"]["series"]) == 25
                responses.append({"url": response.url, "status": response.status,
                                  "origin": body.get("meta", {}).get("origin")})
        page.on("response", record)

        page.goto(args.url, wait_until="networkidle")
        page.wait_for_function("document.querySelectorAll('.data-row-item').length === 6")
        assert page.locator("#home-city-select option").count() == 25
        page.select_option("#home-city-select", "mendoza")
        page.wait_for_function("document.querySelector('#data-source-status').textContent.includes('caché')")
        assert page.locator("#user-location-name").inner_text().startswith("Mendoza")
        page.screenshot(path=str(reports / "home.png"), full_page=True)

        page.goto(args.url + "/explorer?city_id=mendoza&variable=PRECTOTCORR", wait_until="networkidle")
        page.wait_for_function("document.querySelector('#select-city').value === 'mendoza'")
        assert page.locator("#input-latitude").get_attribute("readonly") is not None
        page.uncheck("#toggle-auto-redirect")
        with page.expect_response(lambda response: response.url.endswith("/api/analyze")):
            page.click("#btn-analyze")
        page.wait_for_selector("#analysis-preview-section:not(.d-none)")
        assert "mm/day" in page.locator("#analysis-preview-section").inner_text()
        page.screenshot(path=str(reports / "explorer.png"), full_page=True)
        page.locator("#analysis-preview-section a.btn-primary").click()
        page.wait_for_function("document.querySelectorAll('#seriesTableBody tr').length === 25")
        assert page.locator("#resLocationTitle").inner_text() == "Mendoza"
        assert page.evaluate("Chart.getChart('resultsTrendChart').data.datasets.length") == 4
        with page.expect_download() as download:
            page.click("#btnExportCSV")
        download.value.save_as(str(reports / "results.csv"))
        assert "Origen: cache" in (reports / "results.csv").read_text(encoding="utf-8-sig")
        page.screenshot(path=str(reports / "results.png"), full_page=True)

        page.click("#btnGoToCompare")
        page.wait_for_function("document.querySelectorAll('#cmpTableBody tr').length === 25")
        assert page.locator("#selectPresetA").input_value() == "mendoza"
        assert page.evaluate("Chart.getChart('comparisonChart').data.datasets.length") >= 2
        page.select_option("#selectPresetB", "posadas")
        page.click("#btnRunComparison")
        page.wait_for_function("document.querySelector('#cmpNameB').textContent === 'Posadas'")
        page.screenshot(path=str(reports / "compare.png"), full_page=True)

        # Error simulado explícito: una caída no debe mostrar resultados anteriores ni inventados.
        page.goto(args.url + "/results?city_id=mendoza", wait_until="networkidle")
        page.wait_for_function("document.querySelectorAll('#seriesTableBody tr').length === 25")
        page.route("**/api/analyze", lambda route: route.fulfill(status=503, content_type="application/json",
                   body=json.dumps({"status": "error", "error": {"message": "Fallo simulado de prueba"}})))
        page.click("#btnUpdateResults")
        page.wait_for_function("document.querySelector('#dataModeText').textContent.includes('Fallo simulado')")
        assert page.locator("#results-output").is_hidden()
        page.unroute("**/api/analyze")
        page.click("#btnUpdateResults")
        page.wait_for_function("!document.querySelector('#results-output').hidden")

        page.goto(args.url + "/missions", wait_until="networkidle")
        page.wait_for_selector(".mission-card")
        assert page.locator(".mission-card").count() == 3
        page.select_option("#phenomenon-select", "sequia")
        page.wait_for_function("document.querySelectorAll('#recommendations li').length === 3")
        page.click(".mission-card[data-id='en-busca-del-agua']")
        page.wait_for_selector("#mission-detail:not(.d-none)")
        assert "mm/day" in page.locator("[data-field='facts']").inner_text()
        page.check("#h-decreasing")
        page.locator("#hypothesis-form button[type=submit]").click()
        page.wait_for_function("document.querySelector('#select-city')?.value === 'mendoza'")
        assert page.locator("#select-variable").input_value() == "PRECTOTCORR"
        page.goto(args.url + "/missions?open=misterio-del-viento", wait_until="networkidle")
        page.wait_for_selector("#mission-detail:not(.d-none)")
        page.check("#h-increasing")
        page.locator("#hypothesis-form button[type=submit]").click()
        page.wait_for_function("document.querySelectorAll('#cmpTableBody tr').length === 25")
        assert page.locator("#selectPresetB").input_value() == "buenos-aires"
        assert page.goto(args.url + "/about").status == 200
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(args.url, wait_until="networkidle")
        page.wait_for_function("document.querySelectorAll('.data-row-item').length === 6")
        page.screenshot(path=str(reports / "home-mobile.png"), full_page=True)
        assert not errors, errors
        browser.close()

    report = {"status": "ok", "javascript_errors": errors, "api_responses": responses,
              "checks": ["home", "explorer", "results", "chart", "csv", "compare", "503_and_retry", "missions", "about", "mobile"]}
    (reports / "browser.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "checks": report["checks"], "javascript_errors": errors}, ensure_ascii=False))


if __name__ == "__main__":
    main()
