"""Pruebas heredadas con fixtures sintéticas; no validan tendencias reales."""
"""
EarthLens — Rol 06: Pruebas Unitarias del Motor Estadístico (test_statistics.py)
Valida:
  1. Caso oficial del PDF: Comodoro Rivadavia 2000–2024 (NASA POWER / MERRA-2).
  2. Misiones científicas 01 (Patagonia cambiante), 02 (En busca del agua) y 03 (El misterio del viento).
  3. Regresión lineal (pendiente, cambio por década, cambio total, p-valor e IC 95%).
  4. Agregación anual, filtrado de valores faltantes (-999) y criterios de completitud.
  5. Generación de conclusiones por reglas (p < 0.05 vs p >= 0.05 y nota sobre humedad del suelo).
"""

import unittest

from tests.statistics_fixtures.power import get_reference_series
from services.science.trend_analysis import (
    aggregate_to_annual_series,
    analyze_series,
    compare_two_locations,
    compute_linear_trend,
    evaluate_completeness,
    is_valid_observation,
)


class TestTrendAnalysisResources(unittest.TestCase):
    """Pruebas con los casos de prueba y recursos oficiales del Plan de Desarrollo."""

    def test_recurso_comodoro_rivadavia_t2m_2000_2024(self):
        """
        Página 4 y 6 del PDF: Consulta de prueba Comodoro Rivadavia, 2000–2024 (T2M).
        Debe detectar tendencia ascendente estadísticamente significativa (p < 0.05)
        con pendiente ~0.04 °C/año y cambio total positivo.
        """
        series = get_reference_series(
            latitude=-45.86,
            longitude=-67.50,
            variable="T2M",
            start_year=2000,
            end_year=2024,
        )
        self.assertEqual(len(series), 25)
        self.assertEqual(series[0]["year"], 2000)
        self.assertEqual(series[-1]["year"], 2024)

        result = analyze_series(
            series,
            variable="T2M",
            start_year=2000,
            end_year=2024,
            location_name="Comodoro Rivadavia, Chubut",
        )

        # Verificar estructura exacta del contrato JSON (Página 6)
        self.assertEqual(result["variable"], "T2M")
        self.assertEqual(result["unit"], "deg C")
        self.assertIn("NASA POWER", result["source"])
        self.assertIn("statistics", result)
        self.assertIn("conclusion", result)

        stats = result["statistics"]
        self.assertGreater(stats["slope"], 0.03)
        self.assertAlmostEqual(stats["change_per_decade"], stats["slope"] * 10, places=3)
        self.assertAlmostEqual(stats["total_change"], stats["slope"] * 24, places=2)
        self.assertLess(stats["p_value"], 0.05)
        self.assertTrue(stats["significant"])
        self.assertEqual(stats["direction"], "increasing")

        # El intervalo de confianza al 95% no debe cruzar el cero cuando p < 0.05
        ci_low, ci_high = stats["confidence_interval_95"]
        self.assertGreater(ci_low, 0.0)
        self.assertGreater(ci_high, ci_low)
        self.assertIn("ascendente", result["conclusion"])

    def test_mision_01_patagonia_cambiante_extremos_termicos(self):
        """
        Página 7 — Caso 01 / Patagonia cambiante:
        ¿Está aumentando la temperatura? Evaluar T2M, T2M_MAX y T2M_MIN en Comodoro Rivadavia.
        """
        for var_code in ("T2M", "T2M_MAX", "T2M_MIN"):
            series = get_reference_series(-45.86, -67.50, var_code, 2000, 2024)
            res = analyze_series(series, variable=var_code, start_year=2000, end_year=2024)
            stats = res["statistics"]
            self.assertTrue(stats["significant"], f"{var_code} debe ser significativo")
            self.assertEqual(stats["direction"], "increasing")
            self.assertGreater(stats["change_per_decade"], 0.20)

    def test_mision_02_en_busca_del_agua_precipitacion_y_humedad(self):
        """
        Página 7 — Caso 02 / En busca del agua:
        PRECTOTCORR y RH2M disminuyen; RH2M debe advertir que no equivale a humedad del suelo.
        """
        prec_series = get_reference_series(-45.86, -67.50, "PRECTOTCORR", 2000, 2024)
        prec_res = analyze_series(prec_series, variable="PRECTOTCORR", start_year=2000, end_year=2024)
        self.assertEqual(prec_res["statistics"]["direction"], "decreasing")
        self.assertLess(prec_res["statistics"]["slope"], 0.0)

        rh_series = get_reference_series(-45.86, -67.50, "RH2M", 2000, 2024)
        rh_res = analyze_series(rh_series, variable="RH2M", start_year=2000, end_year=2024)
        self.assertEqual(rh_res["statistics"]["direction"], "decreasing")
        self.assertTrue(rh_res["statistics"]["significant"])
        self.assertIn("no equivale a la humedad del suelo", rh_res["conclusion"])

    def test_mision_03_el_misterio_del_viento_comparacion(self):
        """
        Página 7 — Caso 03 / El misterio del viento:
        Evaluar WS2M y comparar dos ubicaciones (Comodoro Rivadavia vs Ushuaia).
        """
        ws_comodoro = analyze_series(
            get_reference_series(-45.86, -67.50, "WS2M", 2000, 2024),
            variable="WS2M",
            start_year=2000,
            end_year=2024,
        )
        ws_ushuaia = analyze_series(
            get_reference_series(-54.80, -68.30, "WS2M", 2000, 2024),
            variable="WS2M",
            start_year=2000,
            end_year=2024,
        )

        cmp_res = compare_two_locations(
            ws_comodoro,
            ws_ushuaia,
            name_a="Comodoro Rivadavia",
            name_b="Ushuaia",
        )
        self.assertEqual(cmp_res["variable"], "WS2M")
        self.assertIn("deltas", cmp_res)
        self.assertIn("faster_changing_location", cmp_res["deltas"])
        self.assertIn("Comodoro Rivadavia", cmp_res["comparison_conclusion"])


class TestKnownMathematicalCases(unittest.TestCase):
    """Pruebas de casos matemáticos conocidos y de borde."""

    def test_exact_linear_series(self):
        """Una recta exacta y = 10 + 0.05*(x - 2000) debe dar pendiente = 0.05 y R^2 = 1."""
        series = [{"year": yr, "value": 10.0 + 0.05 * (yr - 2000)} for yr in range(2000, 2025)]
        stats = compute_linear_trend(series, start_year=2000, end_year=2024)
        self.assertAlmostEqual(stats["slope"], 0.05, places=5)
        self.assertAlmostEqual(stats["change_per_decade"], 0.50, places=4)
        self.assertAlmostEqual(stats["total_change"], 1.20, places=3)
        self.assertAlmostEqual(stats["r_squared"], 1.0, places=4)
        self.assertLess(stats["p_value"], 0.0001)
        self.assertTrue(stats["significant"])

    def test_non_significant_noisy_series(self):
        """Serie alternante sin tendencia debe reportar p >= 0.05 y explicar que no prueba ausencia de cambio."""
        series = [
            {"year": 2000 + i, "value": 12.0 + (0.4 if i % 2 == 0 else -0.4)}
            for i in range(20)
        ]
        res = analyze_series(series, variable="T2M", start_year=2000, end_year=2019)
        self.assertFalse(res["statistics"]["significant"])
        self.assertGreaterEqual(res["statistics"]["p_value"], 0.05)
        self.assertIn("no demuestra ausencia de cambio", res["conclusion"])

    def test_missing_values_and_nasa_power_monthly_aggregation(self):
        """Verifica limpieza de códigos -999 de NASA POWER, exclusión de mes 13 y criterio de completitud."""
        self.assertFalse(is_valid_observation(-999))
        self.assertFalse(is_valid_observation(-999.0))
        self.assertFalse(is_valid_observation(None))
        self.assertTrue(is_valid_observation(12.5))

        raw_monthly = {}
        # Año 2000 completo (12 meses válidos = 10.0 + mes 13 que debe ignorarse)
        for m in range(1, 13):
            raw_monthly[f"2000{m:02d}"] = 10.0
        raw_monthly["200013"] = 99.9

        # Año 2001 incompleto (solo 4 meses válidos y 8 meses con -999 -> debe descartarse)
        for m in range(1, 5):
            raw_monthly[f"2001{m:02d}"] = 11.0
        for m in range(5, 13):
            raw_monthly[f"2001{m:02d}"] = -999.0

        # Año 2002 con 10 meses válidos (>= 9 meses requeridos -> debe incluirse)
        for m in range(1, 11):
            raw_monthly[f"2002{m:02d}"] = 12.0
        raw_monthly["200211"] = -999.0
        raw_monthly["200212"] = -999.0

        annual = aggregate_to_annual_series(raw_monthly, start_year=2000, end_year=2002)
        years = [item["year"] for item in annual]
        self.assertEqual(years, [2000, 2002])
        self.assertAlmostEqual(annual[0]["value"], 10.0, places=3)
        self.assertAlmostEqual(annual[1]["value"], 12.0, places=3)

        comp = evaluate_completeness(annual, start_year=2000, end_year=2002, min_valid_years=2)
        self.assertEqual(comp["missing_years"], [2001])


if __name__ == "__main__":
    unittest.main()
