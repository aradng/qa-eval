-- M4 — the desk moves to metric tons. Data only; no DDL changes.
-- 1 metric ton of crude is roughly 7.33 barrels.
update trades
   set volume = volume / 7.33,
       price  = price * 7.33;
