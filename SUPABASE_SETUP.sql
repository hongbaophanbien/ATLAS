create table if not exists public.atlas_snapshots (
    id text primary key,
    updated_at timestamptz not null default now(),
    payload jsonb not null
);

create table if not exists public.atlas_settings (
    id text primary key,
    updated_at timestamptz not null default now(),
    watchlist jsonb not null default '[]'::jsonb,
    benchmark text not null default 'QQQ'
);

alter table public.atlas_snapshots enable row level security;
alter table public.atlas_settings enable row level security;

drop policy if exists "atlas snapshots read" on public.atlas_snapshots;
create policy "atlas snapshots read"
on public.atlas_snapshots for select using (true);

drop policy if exists "atlas settings read" on public.atlas_settings;
create policy "atlas settings read"
on public.atlas_settings for select using (true);

-- Writes use server-side service-role keys stored only in Secrets.
