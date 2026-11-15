# Brings the cluster back after ALL database nodes went down together (power cut, host crash).
#
# Each node refuses to start a new cluster unless it was the last one to leave
# (safe_to_bootstrap), because starting from a node that is behind loses committed
# reservations. This script finds the most advanced node with `mariadbd --wsrep-recover`,
# marks only that one safe, and starts it first. Run it from app.
#
# Not needed when at least one node is still running: stopped nodes rejoin by themselves.
# docker writes progress to stderr, so errors are checked explicitly below instead of stopping on it.
$ErrorActionPreference = 'Continue'
$nodes = 'galera1', 'galera2', 'galera3'
$project = if ($env:COMPOSE_PROJECT_NAME) { $env:COMPOSE_PROJECT_NAME } else { "pistas" }

foreach ($n in $nodes) { docker compose stop $n 2>$null | Out-Null }

$cnf = (Resolve-Path (Join-Path $PSScriptRoot 'galera.cnf')).Path
$best = $null
$bestSeq = -2
foreach ($n in $nodes) {
  $vol = "${project}_${n}-data"
  $out = docker run --rm -v "${vol}:/var/lib/mysql" -v "${cnf}:/etc/mysql/conf.d/galera.cnf:ro" `
    --entrypoint mariadbd mariadb:11.4 --user=mysql --wsrep-recover 2>&1
  $line = $out | Select-String 'Recovered position:\s*\S+:(-?\d+)' | Select-Object -Last 1
  $seq = if ($line) { [int]$line.Matches[0].Groups[1].Value } else { -1 }
  Write-Host "$n recovered position (seqno): $seq"
  if ($seq -gt $bestSeq) { $best = $n; $bestSeq = $seq }
}
if ($bestSeq -lt 0) { throw 'Could not recover a position from any node. Do not force a bootstrap blindly.' }

Write-Host "Bootstrapping from $best (seqno $bestSeq)"
docker run --rm -v "${project}_${best}-data:/var/lib/mysql" --entrypoint sh mariadb:11.4 `
  -c "sed -i 's/safe_to_bootstrap: 0/safe_to_bootstrap: 1/' /var/lib/mysql/grastate.dat"

$env:BOOTSTRAP_NODE = $best
docker compose up -d $best
Write-Host 'Waiting for the first node to be Synced...'
for ($i = 0; $i -lt 60; $i++) {
  Start-Sleep 2
  if ((docker compose ps $best --format '{{.Health}}') -eq 'healthy') { break }
}
foreach ($n in $nodes) { if ($n -ne $best) { docker compose up -d $n } }
docker compose up -d
foreach ($n in $nodes) { docker update --restart=unless-stopped (docker compose ps -q $n) | Out-Null }
Write-Host 'Done. Check: docker compose ps'



