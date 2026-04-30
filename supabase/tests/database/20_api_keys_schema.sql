-- 20_api_keys_schema.sql
-- Asserts the api_keys table has the expected shape.

begin;
select plan(8);

select has_table('public', 'api_keys', 'api_keys table exists');
select has_column('public', 'api_keys', 'user_id', 'has user_id');
select has_column('public', 'api_keys', 'provider', 'has provider');
select has_column('public', 'api_keys', 'key_encrypted', 'has key_encrypted');
select col_type_is(
  'public', 'api_keys', 'key_encrypted', 'bytea',
  'key_encrypted is bytea'
);
select has_column('public', 'api_keys', 'last_used_at', 'has last_used_at');
select has_column('public', 'api_keys', 'created_at', 'has created_at');

-- Composite primary key (user_id, provider)
select col_is_pk(
  'public', 'api_keys', array['user_id', 'provider'],
  '(user_id, provider) is composite PK'
);

select * from finish();
rollback;
