-- Hawkeye BigQuery analytics tables (Layer 2 storage).
-- Dataset: hawkeye  (already created)

CREATE TABLE IF NOT EXISTS `dice-master-the-platform.hawkeye.metrics`
(
  resource_id STRING,
  timestamp TIMESTAMP,
  cpu_percent FLOAT64,
  cpu_percent_avg FLOAT64,
  memory_percent FLOAT64,
  disk_iops FLOAT64,
  network_in_bytes INT64,
  network_out_bytes INT64,
  queries_per_second FLOAT64,
  active_connections INT64,
  replication_lag_ms FLOAT64,
  error_rate_percent FLOAT64,
  error_count INT64,
  uptime_percent FLOAT64,
  incidents_count INT64,
  project_id STRING
)
PARTITION BY DATE(timestamp)
CLUSTER BY resource_id;

CREATE TABLE IF NOT EXISTS `dice-master-the-platform.hawkeye.billing`
(
  resource_id STRING,
  date DATE,
  daily_cost FLOAT64,
  sku STRING,
  month_to_date FLOAT64,
  cost_change_percent FLOAT64,
  anomaly_score FLOAT64,
  project_id STRING
)
PARTITION BY date
CLUSTER BY resource_id;

CREATE TABLE IF NOT EXISTS `dice-master-the-platform.hawkeye.audit_logs`
(
  id STRING,
  timestamp TIMESTAMP,
  user_email STRING,
  user_ip STRING,
  action STRING,
  resource_type STRING,
  resource_id STRING,
  changes STRING,
  status STRING,
  error_message STRING,
  project_id STRING
)
PARTITION BY DATE(timestamp)
CLUSTER BY resource_id;

CREATE TABLE IF NOT EXISTS `dice-master-the-platform.hawkeye.resource_lifecycle`
(
  resource_id STRING,
  event STRING,
  timestamp TIMESTAMP,
  project_id STRING
)
PARTITION BY DATE(timestamp)
CLUSTER BY resource_id;
