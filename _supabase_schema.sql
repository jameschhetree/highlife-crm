-- HighLife CRM — Supabase schema
-- Path (a): publicly accessible per James clarification (no login gate)
-- All policies USING (true) — publishable_key has full CRUD

create extension if not exists "pgcrypto";

-- ────────────────────────────────────────────────────────────────────
-- prospects table
-- Mirrors the structure of /Users/james/highlife-crm/prospects.json
-- All fields stored loosely (text where possible) for forward-compat
-- ────────────────────────────────────────────────────────────────────
create table if not exists prospects (
    id                  text primary key,
    name                text,
    job_title           text,
    company             text,
    source              text,
    email               text,
    phone               text,
    linkedin            text,
    instagram           text,
    youtube             text,
    twitter             text,
    website             text,
    package             text,
    status              text default 'prospect',
    last_contact        text,
    notes               text,
    rating              text,
    feedback            text,
    rated_at            timestamptz,
    graveyard_reason    text,
    pushed_to_clay      boolean default false,
    linkedin_status     text,
    instagram_status    text,
    youtube_status      text,
    location            text,
    -- new shared-backend fields
    seller              text,             -- 'Jaco' | 'Liam' | 'Hayden' | ''
    assigned_seller     text,             -- alias for back-compat
    is_in_crm           boolean default false,
    -- timestamps
    created_at          timestamptz default now(),
    updated_at          timestamptz default now()
);

create index if not exists prospects_status_idx on prospects(status);
create index if not exists prospects_seller_idx on prospects(seller);
create index if not exists prospects_updated_idx on prospects(updated_at desc);

-- ────────────────────────────────────────────────────────────────────
-- prospect_actions table — activity feed
-- ────────────────────────────────────────────────────────────────────
create table if not exists prospect_actions (
    id           bigserial primary key,
    prospect_id  text references prospects(id) on delete cascade,
    actor_name   text not null,
    action_type  text not null,
    payload      jsonb,
    created_at   timestamptz default now()
);

create index if not exists prospect_actions_created_idx on prospect_actions(created_at desc);
create index if not exists prospect_actions_pid_idx on prospect_actions(prospect_id);

-- ────────────────────────────────────────────────────────────────────
-- RLS — path (a): fully open with publishable key
-- ────────────────────────────────────────────────────────────────────
alter table prospects enable row level security;
alter table prospect_actions enable row level security;

drop policy if exists "public read"   on prospects;
drop policy if exists "public insert" on prospects;
drop policy if exists "public update" on prospects;
drop policy if exists "public delete" on prospects;

create policy "public read"   on prospects for select using (true);
create policy "public insert" on prospects for insert with check (true);
create policy "public update" on prospects for update using (true) with check (true);
create policy "public delete" on prospects for delete using (true);

drop policy if exists "public read"   on prospect_actions;
drop policy if exists "public insert" on prospect_actions;
drop policy if exists "public update" on prospect_actions;
drop policy if exists "public delete" on prospect_actions;

create policy "public read"   on prospect_actions for select using (true);
create policy "public insert" on prospect_actions for insert with check (true);
create policy "public update" on prospect_actions for update using (true) with check (true);
create policy "public delete" on prospect_actions for delete using (true);
