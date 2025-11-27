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
           --env GIZMOSQL_PASSWORD="..." \
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
GIZMOSQL_PASSWORD="..." gizmosql_server --port 10501 --print-queries


## Generate the TLS Certs
resources/gen_certs.sh


## Attach the Iceberg Tables
GIZMOSQL_PASSWORD=... gizmosql_server -Q -I "install aws; install httpfs; install iceberg; load aws; load httpfs; load iceberg; CREATE SECRET (TYPE s3, PROVIDER credential_chain); ATTACH $S3TABLE_ARN AS tpch_sf100 (TYPE iceberg, ENDPOINT_TYPE s3_tables);" -T ~/.certs/cert0.pem ~/.certs/cert0.key

## Run a count against one of the Iceberg Tables
gizmosql_client --command Execute --username "..." --password "..." --use-tls --tls-skip-verify --query "SELECT COUNT(*) FROM tpch_sf100.tpch_sf100.supplier;"

Results from endpoint 1 of 1
Schema:
count_star(): int64

Results:
count_star():   [
    1000000
  ]

Total: 1
