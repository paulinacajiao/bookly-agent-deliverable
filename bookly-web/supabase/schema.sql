-- Bookly schema + seed. Mirrors bookly-agent/app/data/mock_store.py (see docs/WEBSITE_DESIGN.md §3).

create table customers (
  email text primary key,
  name  text not null
);

create table books (
  book_id serial primary key,
  title   text not null,
  author  text not null,
  price   numeric(10,2) not null,
  cover_url text
);

create table orders (
  order_id     text primary key,
  email        text references customers(email),
  status       text not null,
  delivered_at timestamptz,
  total        numeric(10,2) not null,
  items        text[] not null,
  tracking     text
);

create table returns (
  return_id  text primary key,
  order_id   text references orders(order_id),
  reason     text,
  amount     numeric(10,2),
  state      text not null,
  created_at timestamptz default now()
);

-- RLS: the browser (anon) may only read books. Orders/customers/returns are
-- reachable by anon solely through lookup_order() below; the agent uses the
-- service role, which bypasses RLS.
alter table customers enable row level security;
alter table books     enable row level security;
alter table orders    enable row level security;
alter table returns   enable row level security;

create policy "books are publicly readable" on books for select to anon, authenticated using (true);

-- Order lookup requires both order id and matching email, so anon can't enumerate orders.
create or replace function lookup_order(p_order_id text, p_email text)
returns table (order_id text, status text, delivered_at timestamptz, total numeric, items text[], tracking text)
language sql
stable
security definer
set search_path = public
as $$
  select o.order_id, o.status, o.delivered_at, o.total, o.items, o.tracking
  from orders o
  where o.order_id = upper(trim(p_order_id))
    and o.email = lower(trim(p_email));
$$;

revoke all on function lookup_order(text, text) from public;
grant execute on function lookup_order(text, text) to anon, authenticated;

-- Seed ---------------------------------------------------------------------

insert into customers (email, name) values
  ('jane@email.com',   'Jane Doe'),
  ('carlos@email.com', 'Carlos Ruiz');

insert into books (title, author, price, cover_url) values
  ('The Midnight Library', 'Matt Haig', 24.00, 'https://covers.openlibrary.org/b/isbn/9780525559474-L.jpg'),
  ('Sapiens (Hardcover)', 'Yuval Noah Harari', 65.00, 'https://covers.openlibrary.org/b/isbn/9780062316097-L.jpg'),
  ('Educated', 'Tara Westover', 24.00, 'https://covers.openlibrary.org/b/isbn/9780399590504-L.jpg'),
  ('Atomic Habits', 'James Clear', 30.00, 'https://covers.openlibrary.org/b/isbn/9780735211292-L.jpg'),
  ('Project Hail Mary', 'Andy Weir', 18.00, 'https://covers.openlibrary.org/b/isbn/9780593135204-L.jpg'),
  ('The Creative Act', 'Rick Rubin', 55.00, 'https://covers.openlibrary.org/b/isbn/9780593652886-L.jpg'),
  ('Circe', 'Madeline Miller', 17.50, 'https://covers.openlibrary.org/b/isbn/9780316556347-L.jpg'),
  ('Klara and the Sun', 'Kazuo Ishiguro', 16.00, 'https://covers.openlibrary.org/b/isbn/9780593318171-L.jpg'),
  ('Tomorrow, and Tomorrow, and Tomorrow', 'Gabrielle Zevin', 21.00, 'https://covers.openlibrary.org/b/isbn/9780593321201-L.jpg'),
  ('Dune', 'Frank Herbert', 19.99, 'https://covers.openlibrary.org/b/isbn/9780441172719-L.jpg');

-- delivered_at is relative to now() so the 30-day return window logic stays valid.
insert into orders (order_id, email, status, delivered_at, total, items, tracking) values
  ('ORD-1001', 'jane@email.com',   'delivered',  now() - interval '5 days',  24.00, '{"The Midnight Library"}',            '1Z-JANE-1001'),
  ('ORD-1002', 'jane@email.com',   'delivered',  now() - interval '10 days', 89.00, '{"Sapiens (Hardcover)","Educated"}', '1Z-JANE-1002'),
  ('ORD-1003', 'carlos@email.com', 'delivered',  now() - interval '45 days', 30.00, '{"Atomic Habits"}',                   '1Z-CARL-1003'),
  ('ORD-1004', 'carlos@email.com', 'shipped',    null,                       18.00, '{"Project Hail Mary"}',               '1Z-CARL-1004'),
  ('ORD-1005', 'jane@email.com',   'processing', null,                       55.00, '{"The Creative Act"}',                null);
