-- 006: a reservation is for an aircraft (its registration, e.g. CS-TNP), not for a flight number.
-- The same airframe changes flight number between landing and departure, so the registration is
-- the identity. The arrival flight number and the ICAO code of the airport of origin are kept as
-- information about the arrival. `flight_number` now means the arrival flight.
--
-- Existing rows: registration = their old flight number, origin = 'ZZZZ' (ICAO "unknown").

ALTER TABLE reservation
  ADD COLUMN registration VARCHAR(10) NOT NULL DEFAULT '' AFTER stand_id,
  ADD COLUMN origin       CHAR(4)     NOT NULL DEFAULT 'ZZZZ' AFTER flight_number;
UPDATE reservation SET registration = flight_number WHERE registration = '';

-- ANA's "this aircraft may not return to this stand" is keyed by registration from now on.
ALTER TABLE removed_assignment
  ADD COLUMN registration VARCHAR(10) NOT NULL DEFAULT '' AFTER company,
  ADD KEY ix_removed_registration (company, registration);
UPDATE removed_assignment SET registration = flight_number WHERE registration = '';
