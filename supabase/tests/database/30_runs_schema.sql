-- 30_runs_schema.sql
-- Asserts the runs table has the expected shape.

begin;
select plan(10);

select has_table('public', 'runs', 'runs table exists');
select has_column('public', 'runs', 'id', 'has id');
select col_type_is('public', 'runs', 'id', 'uuid', 'id is uuid');
select col_is_pk('public', 'runs', 'id', 'id is PK');

select has_column('public', 'runs', 'user_id', 'has user_id');
select has_column('public', 'runs', 'ticker', 'has ticker');
select has_column('public', 'runs', 'trade_date', 'has trade_date');
select has_column('public', 'runs', 'status', 'has status');
select col_type_is('public', 'runs', 'config', 'jsonb', 'config is jsonb');
select col_type_is('public', 'runs', 'events', 'jsonb', 'events is jsonb');

select * from finish();
rollback;
