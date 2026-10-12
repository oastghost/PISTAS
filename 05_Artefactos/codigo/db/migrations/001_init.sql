-- 001: initial schema. InnoDB only, every table has a primary key (Galera requirement).
--
-- The one rule that must never break: a stand never has two overlapping reservations.
-- It is enforced by stand_block, which holds one row per ACTIVE reservation, with
-- UNIQUE (stand_id, occupied WITHOUT OVERLAPS). Checked on InnoDB and on a 3-node Galera
-- cluster, see 04_Documentacao_Tecnica/spike-sem-sobreposicao.md.

CREATE TABLE app_user (
  id            BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
  username      VARCHAR(40)  NOT NULL,
  password_hash VARCHAR(255) NOT NULL,           -- Argon2id with salt
  name          VARCHAR(80)  NOT NULL,
  role          ENUM('despachante','ana','controlador','handler') NOT NULL,
  company       VARCHAR(40)  NULL,               -- airline or handling company
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_user_username (username)
) ENGINE=InnoDB;

CREATE TABLE stand (
  id             VARCHAR(8)    NOT NULL PRIMARY KEY,
  name           VARCHAR(40)   NOT NULL,
  apron          VARCHAR(20)   NOT NULL,
  critical       VARCHAR(20)   NOT NULL,         -- critical aircraft as written in the AIP
  category       CHAR(1)       NOT NULL,
  max_wingspan_m DECIMAL(5,2)  NOT NULL
) ENGINE=InnoDB;

CREATE TABLE aircraft_type (
  code       VARCHAR(8)   NOT NULL PRIMARY KEY,
  label      VARCHAR(40)  NOT NULL,
  category   CHAR(1)      NOT NULL,
  wingspan_m DECIMAL(5,2) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE reservation (
  id            CHAR(36)    NOT NULL PRIMARY KEY,
  request_id    CHAR(36)    NOT NULL,            -- client-generated, makes the request idempotent
  stand_id      VARCHAR(8)  NOT NULL,
  flight_number VARCHAR(10) NOT NULL,
  company       VARCHAR(40) NOT NULL,
  aircraft_type VARCHAR(8)  NOT NULL,
  starts_at     DATETIME    NOT NULL,            -- UTC
  ends_at       DATETIME    NOT NULL,            -- UTC
  status        ENUM('approved','removed') NOT NULL DEFAULT 'approved',
  handler       VARCHAR(40) NULL,                -- ground handling company, if requested
  created_by    BIGINT      NOT NULL,
  created_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_reservation_request (request_id),
  KEY ix_reservation_stand (stand_id, starts_at),
  CONSTRAINT fk_reservation_stand    FOREIGN KEY (stand_id)      REFERENCES stand (id),
  CONSTRAINT fk_reservation_aircraft FOREIGN KEY (aircraft_type) REFERENCES aircraft_type (code),
  CONSTRAINT fk_reservation_user     FOREIGN KEY (created_by)    REFERENCES app_user (id),
  CONSTRAINT ck_reservation_times    CHECK (ends_at > starts_at)
) ENGINE=InnoDB;

-- Active reservations only. occupied = [starts_at, ends_at + 30 min), the 30 minutes being the
-- turnaround gap (provisional). Removing a reservation deletes its block in the same
-- transaction that marks it removed and writes the notice.
CREATE TABLE stand_block (
  id             BIGINT      NOT NULL AUTO_INCREMENT PRIMARY KEY,
  reservation_id CHAR(36)    NOT NULL,
  stand_id       VARCHAR(8)  NOT NULL,
  occupied_from  DATETIME    NOT NULL,
  occupied_to    DATETIME    NOT NULL,
  PERIOD FOR occupied(occupied_from, occupied_to),
  UNIQUE KEY no_overlap (stand_id, occupied WITHOUT OVERLAPS),
  UNIQUE KEY uq_block_reservation (reservation_id),
  CONSTRAINT fk_block_reservation FOREIGN KEY (reservation_id) REFERENCES reservation (id),
  CONSTRAINT fk_block_stand       FOREIGN KEY (stand_id)       REFERENCES stand (id)
) ENGINE=InnoDB;

-- A flight ANA removed may not be put back on that stand.
CREATE TABLE removed_assignment (
  id            BIGINT      NOT NULL AUTO_INCREMENT PRIMARY KEY,
  company       VARCHAR(40) NOT NULL,
  flight_number VARCHAR(10) NOT NULL,
  stand_id      VARCHAR(8)  NOT NULL,
  created_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ix_removed_flight (company, flight_number),
  CONSTRAINT fk_removed_stand FOREIGN KEY (stand_id) REFERENCES stand (id)
) ENGINE=InnoDB;

CREATE TABLE notice (
  id             CHAR(36)    NOT NULL PRIMARY KEY,
  reservation_id CHAR(36)    NOT NULL,
  company        VARCHAR(40) NOT NULL,
  message        TEXT        NOT NULL,
  created_at     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ix_notice_company (company, created_at),
  CONSTRAINT fk_notice_reservation FOREIGN KEY (reservation_id) REFERENCES reservation (id)
) ENGINE=InnoDB;

CREATE TABLE report (
  id             CHAR(36)    NOT NULL PRIMARY KEY,
  reservation_id CHAR(36)    NOT NULL,
  author_id      BIGINT      NOT NULL,
  text           VARCHAR(500) NOT NULL,
  created_at     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_report_reservation FOREIGN KEY (reservation_id) REFERENCES reservation (id),
  CONSTRAINT fk_report_author      FOREIGN KEY (author_id)      REFERENCES app_user (id)
) ENGINE=InnoDB;

CREATE TABLE audit_log (
  id         BIGINT      NOT NULL AUTO_INCREMENT PRIMARY KEY,
  at         DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  user_id    BIGINT      NULL,
  username   VARCHAR(40) NULL,
  action     VARCHAR(40) NOT NULL,               -- login, login_failed, ana_removal
  detail     VARCHAR(255) NULL
) ENGINE=InnoDB;
