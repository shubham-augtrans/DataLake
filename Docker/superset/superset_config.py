# Local-dev config, deliberately relaxed to match this project's existing
# trust level (shared plaintext credentials, CORS_ALLOW_ALL_ORIGINS=True,
# Metabase's own "public link" sharing already used the same trade-off).
#
# - PUBLIC_ROLE_LIKE lets an unauthenticated request view any dashboard
#   that has been explicitly published (SupersetClient.create_public_link
#   sets "published": true) - Superset's closest equivalent to Metabase's
#   one-click public link, since Superset has no built-in public-link API.
# - The X-Frame-Options/CSP override lets the Angular app (localhost:4200)
#   embed a published dashboard in an <iframe>, same purpose as Metabase's
#   public-link pages being the one iframe-able view in that stack.
import os

SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "datalake-superset-dev-secret-change-me")

SQLALCHEMY_DATABASE_URI = os.environ.get(
    "SUPERSET_SQLALCHEMY_DATABASE_URI",
    "postgresql://shubham:Shubham%40123456@postgres:5432/superset",
)

PUBLIC_ROLE_LIKE = "Gamma"

HTTP_HEADERS = {}
TALISMAN_ENABLED = False
X_FRAME_OPTIONS = "ALLOWALL"

CONTENT_SECURITY_POLICY_WARNING = False
