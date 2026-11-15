-- 004: first-login password change.
--
-- An account created by the supervisor, or whose password the supervisor reset, carries a
-- password somebody else knows. must_change_password stays 1 until the owner sets their own.
-- The backend refuses everything except "who am I" and "change password" while it is set.

ALTER TABLE app_user ADD COLUMN must_change_password TINYINT(1) NOT NULL DEFAULT 0 AFTER active;
