-- Agent Phase 5 migration, applied on top of bookly-web/supabase/schema.sql.
-- Adds what the agent needs beyond the storefront schema:
--   * DB-generated ids for returns (RET-0001) and escalations (ESC-0001)
--   * the escalations table (data contract change from agent Phase 4)
--   * reset_demo(): restore the demo seed with dates relative to now(), so the
--     return-window cases stay valid on any day and demo runs are repeatable.
-- Service role only: the browser (anon) gets no access to any of it.

create sequence if not exists return_seq;
create sequence if not exists escalation_seq;

alter table returns
  alter column return_id set default 'RET-' || lpad(nextval('return_seq')::text, 4, '0');

create table if not exists escalations (
  ticket_id  text primary key
             default 'ESC-' || lpad(nextval('escalation_seq')::text, 4, '0'),
  order_id   text references orders(order_id),   -- null when not about an order
  summary    text not null,
  state      text not null default 'open',
  created_at timestamptz default now()
);

-- RLS on, no policies: only the service role (which bypasses RLS) can touch it.
alter table escalations enable row level security;

create or replace function reset_demo()
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  -- "where true": Supabase's API blocks DELETE without a WHERE clause.
  delete from escalations where true;
  delete from returns where true;
  perform setval('return_seq', 1, false);
  perform setval('escalation_seq', 1, false);

  insert into customers (email, name) values
    ('jane@email.com',   'Jane Doe'),
    ('carlos@email.com', 'Carlos Ruiz')
  on conflict (email) do update set name = excluded.name;

  insert into orders (order_id, email, status, delivered_at, total, items, tracking) values
    ('ORD-1001', 'jane@email.com',   'delivered',  now() - interval '5 days',  24.00, '{"The Midnight Library"}',            '1Z-JANE-1001'),
    ('ORD-1002', 'jane@email.com',   'delivered',  now() - interval '10 days', 89.00, '{"Sapiens (Hardcover)","Educated"}', '1Z-JANE-1002'),
    ('ORD-1003', 'carlos@email.com', 'delivered',  now() - interval '45 days', 30.00, '{"Atomic Habits"}',                   '1Z-CARL-1003'),
    ('ORD-1004', 'carlos@email.com', 'shipped',    null,                       18.00, '{"Project Hail Mary"}',               '1Z-CARL-1004'),
    ('ORD-1005', 'jane@email.com',   'processing', null,                       55.00, '{"The Creative Act"}',                null)
  on conflict (order_id) do update set
    email = excluded.email, status = excluded.status,
    delivered_at = excluded.delivered_at, total = excluded.total,
    items = excluded.items, tracking = excluded.tracking;
end;
$$;

revoke all on function reset_demo() from public, anon, authenticated;
grant execute on function reset_demo() to service_role;
