#!/usr/bin/env bash
# Démarre Airflow en un seul conteneur : base de données, compte admin, puis scheduler + serveur web.
set -euo pipefail

airflow db migrate

# Compte utilisé par l'interface et par l'API REST (authentification basique). Idempotent.
airflow users create --role Admin \
  --username "${AIRFLOW_ADMIN_USER:-admin}" --password "${AIRFLOW_ADMIN_PASSWORD:-admin}" \
  --firstname Admin --lastname Jumeau --email admin@example.com || true

# `standalone` supervise scheduler, serveur web et triggerer, et garde l'exécuteur/la base de l'environnement
exec airflow standalone
