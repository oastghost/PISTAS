# Runs the overlap spike against a throwaway MariaDB container. Needs Docker.
$ErrorActionPreference = 'Stop'
$c = 'pistas-spike'
$sql = Join-Path $PSScriptRoot 'overlap.sql'

docker cp $sql "${c}:/tmp/overlap.sql"
Write-Host '--- 1. schema and sequential checks (the 2nd insert must fail with 1062) ---'
docker exec $c sh -c "mariadb -uroot -pspike spike --force < /tmp/overlap.sql 2>&1"

Write-Host '--- 2. adjacent period on same stand (08:00-10:00), must succeed ---'
docker exec $c mariadb -uroot -pspike spike -e "INSERT INTO reservation (stand_id, starts_at, ends_at, flight) VALUES ('114','2026-10-12 08:00','2026-10-12 10:00','A3'); SELECT 'adjacent ok' AS result;"

Write-Host '--- 3. same period, other stand, must succeed ---'
docker exec $c mariadb -uroot -pspike spike -e "INSERT INTO reservation (stand_id, starts_at, ends_at, flight) VALUES ('115','2026-10-12 06:00','2026-10-12 08:00','A4'); SELECT 'other stand ok' AS result;"

Write-Host '--- 4. 20 concurrent inserts for the same stand and period: exactly 1 must win ---'
docker cp (Join-Path $PSScriptRoot 'concurrent.sh') "${c}:/tmp/concurrent.sh"
docker exec $c sh /tmp/concurrent.sh
