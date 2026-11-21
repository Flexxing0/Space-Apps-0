"""Contratos de páginas sin acceso a datos ni proveedores remotos."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import create_app


class ProductPageTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.client = create_app({"TESTING": True, "CACHE_DIR": Path(directory.name)}).test_client()

    def test_new_pages_render_without_scientific_computation_or_network(self):
        with patch("requests.sessions.Session.request", side_effect=AssertionError("red prohibida")), \
                patch("services.science.analysis_service.AnalysisService.results", side_effect=AssertionError("análisis prohibido")):
            for page, asset in (("/radar", "radar.js"), ("/fingerprint", "fingerprint.js")):
                with self.subTest(page=page):
                    response = self.client.get(page)
                    self.assertEqual(response.status_code, 200)
                    html = response.get_data(as_text=True)
                    self.assertNotIn("{%", html)
                    self.assertIn("Evidencia provisional", html)
                    self.assertIn("no son descubrimientos confirmados", html)
                    self.assertIn("/static/js/products/" + asset, html)
                    self.assertIn('aria-current="page"', html)

    def test_navigation_reaches_products_from_every_existing_page(self):
        for page in ("/", "/explorer", "/results", "/compare", "/missions", "/about", "/radar", "/fingerprint"):
            with self.subTest(page=page):
                html = self.client.get(page).get_data(as_text=True)
                self.assertEqual(html.count('<nav '), 1)
                self.assertIn('href="/radar"', html)
                self.assertIn('href="/fingerprint"', html)
                self.assertIn('aria-label="Navegación principal"', html)
                if page == "/":
                    self.assertIn('/static/js/time-machine/workspace.js', html)
                    self.assertIn('id="scrubber"', html)
                    self.assertNotIn('home-location-map', html)

    def test_product_assets_are_served(self):
        for asset in ("js/products/products.js", "js/products/radar.js", "js/products/fingerprint.js", "css/pages/products.css"):
            with self.subTest(asset=asset), self.client.get("/static/" + asset) as response:
                self.assertEqual(response.status_code, 200)
                self.assertGreater(len(response.data), 100)


if __name__ == "__main__":
    unittest.main()
