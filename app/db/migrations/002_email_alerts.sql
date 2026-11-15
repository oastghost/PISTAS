-- 002: e-mail alerts to ANA when a controller reports a flight.
--
-- Transactional outbox: the report and one email_outbox row per ANA recipient are written in
-- the same transaction, so a report never exists without its pending e-mails and an SMTP outage
-- never loses or blocks anything. A worker in every backend sends the pending rows.

ALTER TABLE app_user ADD COLUMN email VARCHAR(120) NULL AFTER name;

CREATE TABLE email_outbox (
  id            BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
  report_id     CHAR(36)     NOT NULL,
  recipient     VARCHAR(120) NOT NULL,
  subject       VARCHAR(200) NOT NULL,
  body          TEXT         NOT NULL,
  status        ENUM('pending','sent','failed') NOT NULL DEFAULT 'pending',
  attempts      INT          NOT NULL DEFAULT 0,
  next_try_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- also the claim lease
  last_error    VARCHAR(255) NULL,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  sent_at       DATETIME     NULL,
  sent_by       VARCHAR(64)  NULL,                                -- backend that delivered it
  KEY ix_outbox_due (status, next_try_at),
  UNIQUE KEY uq_outbox_report_recipient (report_id, recipient),
  CONSTRAINT fk_outbox_report FOREIGN KEY (report_id) REFERENCES report (id)
) ENGINE=InnoDB;
