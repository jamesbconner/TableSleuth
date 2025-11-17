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


Install GizmoSQL ...

https://github.com/gizmodata/gizmosql/releases/download/v1.12.10/gizmosql_cli_macos_arm64.zip (to /usr/local/bin/)

or

brew install cmake boost ninja
git clone https://github.com/gizmodata/gizmosql --recurse-submodules
cd gizmosql
cmake -S . -B build -G Ninja -DCMAKE_INSTALL_PREFIX=/usr/local
cmake --build build --target install


Start GizmoSQL
GIZMOSQL_PASSWORD="gizmosql_password" gizmosql_server --port 10501 --print-queries







pandas==2.3.*
duckdb==1.4.*
click==8.3.*
pyarrow==22.0.0
adbc-driver-flightsql==1.8.*
adbc-driver-manager==1.8.*
