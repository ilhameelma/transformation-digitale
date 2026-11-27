# Conteneur Airflow + SUMO. SUMO est installé dans l'image : les tâches lancent `sumo` et `duarouter`
# directement, sans DockerOperator (pas de socket Docker à monter).
# Règles d'équipe : Python 3.11 et eclipse-sumo==1.28.0 partout.
FROM apache/airflow:2.10.5-python3.11

USER root
# Mêmes bibliothèques système que traffic/Dockerfile.traffic (base Debian bookworm)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libatomic1 \
    libx11-6 libxext6 libxrender1 libxcursor1 libxft2 libxi6 libxrandr2 \
    libgl1 libglu1-mesa libfontconfig1 libxerces-c3.2 \
    && rm -rf /var/lib/apt/lists/*

USER airflow
# Connexion lente : réessais et reprise, comme dans traffic/Dockerfile.traffic
RUN pip install --no-cache-dir --retries 10 --timeout 120 eclipse-sumo==1.28.0

ENV SUMO_HOME=/home/airflow/.local/lib/python3.11/site-packages/sumo
# Le build échoue ici, et pas au premier run, si SUMO ou SUMO_HOME ne sont pas là où on les attend
RUN test -d "$SUMO_HOME" && sumo --version | head -1 && duarouter --version | head -1

ENV PYTHONPATH=/opt/airflow/include \
    DATA_DIR=/data SIM_DIR=/sim TRAFFIC_DIR=/traffic

# Copie de secours ; docker-compose monte ces dossiers pour voir les modifications sans reconstruire
COPY --chown=airflow:root dags /opt/airflow/dags
COPY --chown=airflow:root include /opt/airflow/include
COPY --chown=airflow:root entrypoint.sh /opt/airflow/entrypoint-jumeau.sh
# sed : tolère un entrepôt Git Windows qui aurait converti les fins de ligne en CRLF
RUN sed -i 's/\r$//' /opt/airflow/entrypoint-jumeau.sh && chmod +x /opt/airflow/entrypoint-jumeau.sh

# On garde l'ENTRYPOINT de l'image Airflow (dumb-init : nettoie les processus SUMO terminés)
CMD ["bash", "/opt/airflow/entrypoint-jumeau.sh"]
