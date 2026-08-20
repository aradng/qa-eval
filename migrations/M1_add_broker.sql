-- M1 — add a nullable broker column. Not all trades have a broker.
alter table trades add column broker text null;
