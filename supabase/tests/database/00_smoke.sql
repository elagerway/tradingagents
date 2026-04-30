-- 00_smoke.sql
-- Sanity check that pgTAP runs at all. Should always pass.

begin;
select plan(1);

select pass('pgTAP test runner is alive');

select * from finish();
rollback;
