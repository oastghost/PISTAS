-- 007: a dispatcher can dismiss an ANA notice once read. Dismissal is per person: a colleague at
-- the same airline still sees the notice until they dismiss it too. The notice itself is kept.

CREATE TABLE notice_read (
  notice_id CHAR(36)  NOT NULL,
  user_id   BIGINT    NOT NULL,
  read_at   DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (notice_id, user_id),
  CONSTRAINT fk_notice_read_notice FOREIGN KEY (notice_id) REFERENCES notice (id),
  CONSTRAINT fk_notice_read_user   FOREIGN KEY (user_id)   REFERENCES app_user (id)
) ENGINE=InnoDB;
