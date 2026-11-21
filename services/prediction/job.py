"""Coordinación offline. Ningún proceso y ningún proveedor se activa por defecto."""

from dataclasses import asdict, dataclass

from services.geography.cities import get_city
from services.prediction.contracts import digest
from services.storage.predictions import PredictionStore, RunClaim


@dataclass(frozen=True)
class JobLimits:
    max_history_points: int = 2048
    max_horizon: int = 168
    daily_budget_micros: int = 0

    def __post_init__(self):
        if not all(type(v) is int for v in (self.max_history_points, self.max_horizon, self.daily_budget_micros)) or (
                self.max_history_points < 1 or self.max_horizon < 1 or self.daily_budget_micros < 0):
            raise ValueError('Límites del proceso inválidos.')


class PredictionJob:
    def __init__(self, store: PredictionStore, *, enabled=False, limits=JobLimits(), city_lookup=get_city):
        self.store = store
        self.enabled = enabled is True
        self.limits = limits
        self.city_lookup = city_lookup

    def run(self, provider, plan, *, estimated_cost_micros, retry_failed=False):
        if not self.enabled or not provider.enabled:
            return RunClaim('disabled')
        city = self.city_lookup(plan.key.city_id)
        if (city is None or city['country_code'] != 'AR'
                or (city['latitude'], city['longitude']) != (plan.key.latitude, plan.key.longitude)):
            raise ValueError('El cálculo requiere coordenadas de una ciudad argentina del catálogo.')
        history_size = len(plan.history.observations) if plan.history else 0
        if history_size > self.limits.max_history_points or plan.steps > self.limits.max_horizon:
            raise ValueError('La selección supera los límites de volumen.')
        if type(estimated_cost_micros) is not int or estimated_cost_micros < 0:
            raise ValueError('La ejecución requiere una estimación no negativa.')
        identity = {'provider': provider.name, 'provider_revision': provider.revision,
                    'key': asdict(plan.key), 'first_target': plan.first_target, 'steps': plan.steps,
                    'source_revision': plan.source_revision,
                    'history_hash': digest(asdict(plan.history)) if plan.history else None}
        claim = self.store.claim(digest(identity), identity, estimated_cost_micros=estimated_cost_micros,
                                 daily_budget_micros=self.limits.daily_budget_micros,
                                 retry_failed=retry_failed)
        if claim.status != 'claimed':
            return claim
        try:
            batch = provider.produce(plan)
            if batch.key != plan.key or batch.provider != provider.name or (
                    tuple(p.target for p in batch.points) != plan.targets()):
                raise ValueError('El proveedor devolvió una selección distinta.')
            version_id = self.store.publish(claim.run_id, batch)
        except Exception as error:
            self.store.fail(claim.run_id, type(error).__name__)
            raise
        return RunClaim('completed', claim.run_id, version_id)
