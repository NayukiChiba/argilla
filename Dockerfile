ARG ARGILLA_BASE_IMAGE=argilla/argilla-server:v2.8.0
FROM ${ARGILLA_BASE_IMAGE}

USER root
RUN pip install --no-cache-dir huggingface-hub==0.36.2
COPY --chown=argilla:argilla argilla-server/src/argilla_server /opt/argilla-source/argilla_server
COPY --chown=argilla:argilla argilla/src/argilla /opt/argilla-source/argilla
COPY --chown=argilla:argilla argilla-frontend/dist /opt/argilla-source/argilla_server/static
COPY --chown=argilla:argilla deploy/docker/start.py /opt/argilla-source/start.py
ENV PYTHONPATH=/opt/argilla-source
ARG VCS_REF=unknown
LABEL org.opencontainers.image.revision=${VCS_REF}
USER argilla
CMD ["python", "/opt/argilla-source/start.py"]
