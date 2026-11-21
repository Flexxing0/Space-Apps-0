-- Propuesta para un dataset previamente aprobado en una única ubicación.
-- Sustituir __PROJECT__ y __DATASET__ antes de aplicar. Esta etapa no ejecuta el DDL.
-- BigQuery no arbitra exclusión entre workers: coordinar fuera del almacén analítico.

CREATE TABLE IF NOT EXISTS `__PROJECT__.__DATASET__.historical_series` (
  history_id STRING NOT NULL,
  city_id STRING NOT NULL,
  latitude FLOAT64 NOT NULL,
  longitude FLOAT64 NOT NULL,
  variable STRING NOT NULL,
  unit STRING NOT NULL,
  frequency STRING NOT NULL,
  product STRING NOT NULL,
  observed_at TIMESTAMP NOT NULL,
  value FLOAT64,
  provenance JSON NOT NULL
)
PARTITION BY DATE(observed_at)
CLUSTER BY city_id, variable, frequency, history_id
OPTIONS(require_partition_filter = TRUE);

CREATE TABLE IF NOT EXISTS `__PROJECT__.__DATASET__.prediction_versions` (
  version_id STRING NOT NULL,
  run_id STRING NOT NULL,
  history_id STRING,
  city_id STRING NOT NULL,
  latitude FLOAT64 NOT NULL,
  longitude FLOAT64 NOT NULL,
  variable STRING NOT NULL,
  unit STRING NOT NULL,
  frequency STRING NOT NULL,
  provider STRING NOT NULL,
  kind STRING NOT NULL,
  model STRING NOT NULL,
  model_version STRING,
  generated_at TIMESTAMP,
  published_at TIMESTAMP NOT NULL,
  historical_start TIMESTAMP,
  historical_end TIMESTAMP,
  validation_status STRING NOT NULL,
  provenance JSON NOT NULL,
  point_count INT64 NOT NULL,
  first_target TIMESTAMP NOT NULL,
  last_target TIMESTAMP NOT NULL
)
PARTITION BY DATE(published_at)
CLUSTER BY city_id, variable, provider, version_id;

CREATE TABLE IF NOT EXISTS `__PROJECT__.__DATASET__.prediction_points` (
  version_id STRING NOT NULL,
  city_id STRING NOT NULL,
  variable STRING NOT NULL,
  provider STRING NOT NULL,
  target TIMESTAMP NOT NULL,
  horizon INT64 NOT NULL,
  value FLOAT64,
  interval_lower FLOAT64,
  interval_upper FLOAT64,
  interval_level FLOAT64,
  quantiles ARRAY<STRUCT<quantile FLOAT64, value FLOAT64>>
)
PARTITION BY DATE(target)
CLUSTER BY city_id, variable, provider, version_id
OPTIONS(require_partition_filter = TRUE);

CREATE TABLE IF NOT EXISTS `__PROJECT__.__DATASET__.prediction_runs` (
  run_id STRING NOT NULL,
  request_key STRING NOT NULL,
  attempt INT64 NOT NULL,
  status STRING NOT NULL,
  event_at TIMESTAMP NOT NULL,
  provider STRING NOT NULL,
  city_id STRING NOT NULL,
  variable STRING NOT NULL,
  estimated_cost_micros INT64 NOT NULL,
  details JSON NOT NULL,
  error_code STRING,
  cloud_job_id STRING,
  bytes_billed INT64
)
PARTITION BY DATE(event_at)
CLUSTER BY provider, city_id, variable, run_id;

CREATE TABLE IF NOT EXISTS `__PROJECT__.__DATASET__.prediction_backtests` (
  run_id STRING NOT NULL,
  history_id STRING NOT NULL,
  evaluated_at TIMESTAMP NOT NULL,
  city_id STRING NOT NULL,
  latitude FLOAT64 NOT NULL,
  longitude FLOAT64 NOT NULL,
  variable STRING NOT NULL,
  unit STRING NOT NULL,
  frequency STRING NOT NULL,
  model STRING NOT NULL,
  cut_date DATE NOT NULL,
  training_last_date DATE NOT NULL,
  horizon_days INT64 NOT NULL,
  n INT64 NOT NULL,
  mae FLOAT64 NOT NULL,
  rmse FLOAT64 NOT NULL,
  interval_coverage FLOAT64,
  method STRING NOT NULL
)
PARTITION BY DATE(evaluated_at)
CLUSTER BY city_id, variable, model, history_id;
