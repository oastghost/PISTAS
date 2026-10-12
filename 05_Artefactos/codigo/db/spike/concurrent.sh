#!/bin/sh
# 20 concurrent inserts for the same stand and period. Exactly 1 may win.
mariadb -uroot -pspike spike -e "DELETE FROM reservation WHERE stand_id='200'"
for i in $(seq 1 20); do
  (mariadb -uroot -pspike spike -e "INSERT INTO reservation (stand_id, starts_at, ends_at, flight) VALUES ('200','2026-10-12 12:00','2026-10-12 14:00','C$i')" >/dev/null 2>&1 && echo won) &
done
wait
mariadb -uroot -pspike spike -N -e "SELECT CONCAT('rows for stand 200: ', COUNT(*)) FROM reservation WHERE stand_id='200'"
