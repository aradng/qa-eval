-- M3 — widen volume. Same SQL type, more scale.
alter table trades alter column volume type numeric(18, 6);
