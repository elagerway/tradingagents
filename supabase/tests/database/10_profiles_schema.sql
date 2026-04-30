-- 10_profiles_schema.sql
-- Asserts the profiles table has the expected shape.

begin;
select plan(7);

select has_table('public', 'profiles', 'profiles table exists');

select has_column('public', 'profiles', 'id', 'has id column');
select col_type_is('public', 'profiles', 'id', 'uuid', 'id is uuid');
select col_is_pk('public', 'profiles', 'id', 'id is primary key');

select has_column('public', 'profiles', 'email', 'has email column');
select has_column('public', 'profiles', 'allowed_at', 'has allowed_at column');
select col_type_is(
  'public', 'profiles', 'allowed_at',
  'timestamp with time zone',
  'allowed_at is timestamptz'
);

select * from finish();
rollback;
