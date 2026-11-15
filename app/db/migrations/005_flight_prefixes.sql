-- 005: every airline owns its flight number prefixes (ICAO such as RYR, DLH, optionally IATA
-- such as FR, LH). A dispatcher can only request flights that start with one of them, so
-- RYR1234 can only come from Ryanair. A prefix belongs to exactly one airline.
--
-- Existing reservations are left alone: the rule applies to new requests. An airline with no
-- prefix cannot request stands until the supervisor gives it one.

CREATE TABLE airline_prefix (
  prefix  VARCHAR(3)  NOT NULL PRIMARY KEY,
  airline VARCHAR(40) NOT NULL,
  KEY ix_prefix_airline (airline),
  CONSTRAINT fk_prefix_airline FOREIGN KEY (airline) REFERENCES airline (name)
) ENGINE=InnoDB;
