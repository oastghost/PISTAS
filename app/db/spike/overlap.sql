-- Spike: does MariaDB application-time PERIOD ... WITHOUT OVERLAPS work on InnoDB?
DROP TABLE IF EXISTS reservation;
CREATE TABLE reservation (
  id        BIGINT      NOT NULL AUTO_INCREMENT PRIMARY KEY,
  stand_id  VARCHAR(8)  NOT NULL,
  starts_at DATETIME    NOT NULL,
  ends_at   DATETIME    NOT NULL,
  flight    VARCHAR(10) NOT NULL,
  PERIOD FOR occupied(starts_at, ends_at),
  UNIQUE KEY no_overlap (stand_id, occupied WITHOUT OVERLAPS)
) ENGINE=InnoDB;

-- 1. first reservation: ok
INSERT INTO reservation (stand_id, starts_at, ends_at, flight) VALUES ('114', '2026-10-12 06:00', '2026-10-12 08:00', 'A1');
-- 2. overlapping on same stand: must fail
INSERT INTO reservation (stand_id, starts_at, ends_at, flight) VALUES ('114', '2026-10-12 07:00', '2026-10-12 09:00', 'A2');
