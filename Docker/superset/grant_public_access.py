# Run once via `superset shell < grant_public_access.py` during setup.
#
# PUBLIC_ROLE_LIKE = "Gamma" (superset_config.py) only copies the
# permission-view rows Gamma already had at startup - it does NOT grant
# access to databases/datasets created afterwards (every chart
# SupersetClient builds). Without this, a "published" dashboard still
# 302-redirects anonymous viewers to /dashboard/list/ because the Public
# role has no datasource_access grant for anything the app creates later.
#
# Granting the two blanket ("all_*") permissions instead of a real
# per-object grant is a deliberate, scoped trade-off: it makes every
# dataset/dashboard in THIS Superset instance publicly viewable (read
# only - Public/Gamma has no write permissions), matching the same
# dev-grade trust level as this project's other shared-credential
# services, and is the standard way Superset itself documents running a
# fully-public instance. It does not grant write/admin access.
from superset import security_manager
from superset.extensions import db

public = security_manager.find_role("Public")
pv1 = security_manager.find_permission_view_menu("all_database_access", "all_database_access")
pv2 = security_manager.find_permission_view_menu("all_datasource_access", "all_datasource_access")
if pv1 and pv1 not in public.permissions:
    public.permissions.append(pv1)

if pv2 and pv2 not in public.permissions:
    public.permissions.append(pv2)

db.session.commit()
print(f"Public role now has {len(public.permissions)} permissions.")
