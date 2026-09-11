# Thin extension of the OFFICIAL Superset image - the stock image has no
# Trino driver, and SupersetClient (Backend/core/apps/playground/
# superset_client.py) needs one to register the Lakehouse (Trino) database
# connection the same way MetabaseClient does for Metabase. Same trade-off
# already made for Trino's Ranger plugin - see README.md section 2.
FROM apache/superset:4.1.1

USER root
RUN pip install --no-cache-dir trino sqlalchemy-trino psycopg2-binary
USER superset
