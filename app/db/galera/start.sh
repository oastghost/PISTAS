#!/bin/bash
# Starts one Galera node. All nodes know all peers.
#  - If any peer answers on the Galera port, this node joins it.
#  - If nobody answers and this is the designated bootstrap node, it starts a new cluster.
#    MariaDB itself refuses (safe_to_bootstrap) when this node was not the last one up.
#  - Otherwise it exits and the restart policy tries again, so it never starts a second cluster.
set -u
me=$(hostname)
reachable=0
for peer in galera1 galera2 galera3; do
  [ "$peer" = "$me" ] && continue
  if (exec 3<>"/dev/tcp/$peer/4567") 2>/dev/null; then reachable=1; fi
done

extra=""
if [ "$reachable" = 0 ]; then
  if [ "$me" = "${BOOTSTRAP_NODE:-galera1}" ]; then
    echo "pistas: no peer reachable, bootstrapping a new cluster from $me"
    extra="--wsrep-new-cluster"
  else
    echo "pistas: no peer reachable and $me is not the bootstrap node, retrying shortly"
    sleep 5
    exit 1
  fi
fi
exec docker-entrypoint.sh mariadbd --wsrep-node-name="$me" --wsrep-node-address="$me" $extra
