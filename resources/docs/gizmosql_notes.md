# GizmoSQL

## Repo
https://github.com/gizmodata/gizmosql

## Docker install
docker run --name gizmosql \
           --detach \
           --rm \
           --tty \
           --init \
           --publish 31337:31337 \
           --env TLS_ENABLED="1" \
           --env GIZMOSQL_PASSWORD="gizmosql_password" \
           --env PRINT_QUERIES="1" \
           --volume "$(pwd)/data:/data" \
           --pull always \
           gizmodata/gizmosql:latest
