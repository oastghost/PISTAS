-- 003: airlines as a managed list, a senior ANA role, and switchable accounts.
--
-- A dispatcher belongs to one airline through app_user.company, as before: every dispatcher of
-- an airline sees the same notices and bids in the airline's name. What is new is that the list
-- of airlines is a table, so a typo can no longer create a second "airline", and that the
-- ana_supervisor role can add airlines and dispatcher accounts and disable them.

ALTER TABLE app_user
  MODIFY COLUMN role ENUM('despachante','ana','ana_supervisor','controlador','handler') NOT NULL,
  ADD COLUMN active TINYINT(1) NOT NULL DEFAULT 1 AFTER company;

CREATE TABLE airline (
  name       VARCHAR(40) NOT NULL PRIMARY KEY,   -- same text as app_user.company and reservation.company
  created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

INSERT INTO airline (name) SELECT DISTINCT company FROM app_user WHERE role = 'despachante' AND company IS NOT NULL;
