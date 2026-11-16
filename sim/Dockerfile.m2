FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libatomic1 \
    libx11-6 libxext6 libxrender1 libxcursor1 libxft2 libxi6 libxrandr2 \
    libgl1 libglu1-mesa libfontconfig1 libxerces-c3.2 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir eclipse-sumo==1.28.0 traci==1.28.0 sumolib==1.28.0

ENV SUMO_HOME=/usr/local/lib/python3.11/site-packages/sumo
ENV PATH="/usr/local/bin:${PATH}"

WORKDIR /app
COPY . /app
CMD ["python", "run_test.py"]