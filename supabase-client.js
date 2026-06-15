// HighLife CRM — Supabase client layer
// ─────────────────────────────────────────────────────────────────────
// Drop-in replacement for the old localStorage save/load pattern.
//
// Strategy:
//   1. On boot, fetch all prospects from Supabase into an in-memory cache.
//   2. UI reads stay synchronous against the cache (so renderBoard stays fast).
//   3. Writes update cache immediately, then debounce-flush to Supabase.
//   4. Poll for remote changes every 30s so sellers see each other's edits.
//
// Maps DB snake_case <-> JS camelCase to preserve the existing UI contract.

(function () {
  'use strict';

  const SUPABASE_URL = window.HL_SUPABASE_URL;
  const SUPABASE_KEY = window.HL_SUPABASE_PUBLISHABLE_KEY;
  if (!SUPABASE_URL || !SUPABASE_KEY) {
    console.error('[HL] Supabase config missing — page will not function');
    return;
  }

  const sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY, {
    auth: { persistSession: false },
    realtime: { params: { eventsPerSecond: 5 } },
  });
  window.__hlSupabase = sb;

  // ── In-memory cache ────────────────────────────────────────────────
  let prospectsCache = [];
  let actionsCache = [];
  const dirty = new Map(); // id → pending row patch
  let flushTimer = null;
  const FLUSH_DEBOUNCE_MS = 300;
  const POLL_INTERVAL_MS = 30000;
  const ACTIONS_POLL_MS = 15000;

  // ── Status mapping ──────────────────────────────────────────────────
  const VALID_STATUSES = new Set([
    'new_lead', 'contacted', 'call_booked', 'call_completed',
    'proposal_sent', 'closed_won', 'closed_lost', 'inactive',
  ]);
  function mapStatus(s) {
    if (!s) return 'new_lead';
    if (VALID_STATUSES.has(s)) return s;
    if (s === 'graveyard') return 'inactive';
    return 'new_lead';
  }

  // ── Field mapping ──────────────────────────────────────────────────
  // DB → JS (camelCase the UI already uses)
  function fromDb(r) {
    if (!r) return null;
    return {
      id: r.id,
      name: r.name,
      jobTitle: r.job_title,
      company: r.company,
      source: r.source,
      email: r.email,
      phone: r.phone,
      linkedin: r.linkedin,
      instagram: r.instagram,
      youtube: r.youtube,
      twitter: r.twitter,
      website: r.website,
      package: r.package,
      status: mapStatus(r.status),
      lastContact: r.last_contact,
      notes: r.notes,
      rating: r.rating,
      feedback: r.feedback,
      ratedAt: r.rated_at,
      graveyard_reason: r.graveyard_reason,
      pushedToClay: !!r.pushed_to_clay,
      linkedin_status: r.linkedin_status,
      instagram_status: r.instagram_status,
      youtube_status: r.youtube_status,
      location: r.location,
      seller: r.seller || '',
      is_in_crm: !!r.is_in_crm,
      createdAt: r.created_at,
      updatedAt: r.updated_at,
    };
  }

  // JS → DB
  function toDb(p) {
    return {
      id: p.id,
      name: p.name ?? null,
      job_title: p.jobTitle ?? null,
      company: p.company ?? null,
      source: p.source ?? null,
      email: p.email ?? null,
      phone: p.phone ?? null,
      linkedin: p.linkedin ?? null,
      instagram: p.instagram ?? null,
      youtube: p.youtube ?? null,
      twitter: p.twitter ?? null,
      website: p.website ?? null,
      package: p.package ?? null,
      status: p.status ?? 'prospect',
      last_contact: p.lastContact ?? null,
      notes: p.notes ?? null,
      rating: p.rating ?? null,
      feedback: p.feedback ?? null,
      rated_at: p.ratedAt ?? null,
      graveyard_reason: p.graveyard_reason ?? null,
      pushed_to_clay: !!p.pushedToClay,
      linkedin_status: p.linkedin_status ?? null,
      instagram_status: p.instagram_status ?? null,
      youtube_status: p.youtube_status ?? null,
      location: p.location ?? null,
      seller: p.seller || null,
      is_in_crm: !!p.is_in_crm || p.status === 'added_to_crm',
      created_at: p.createdAt ?? null,
      updated_at: new Date().toISOString(),
    };
  }

  // ── Boot: fetch everything ────────────────────────────────────────
  async function loadAll() {
    // Supabase default page size is 1000; we have ~700 — one fetch.
    const { data, error } = await sb
      .from('prospects')
      .select('*')
      .order('created_at', { ascending: true })
      .limit(2000);
    if (error) {
      console.error('[HL] loadAll error', error);
      return [];
    }
    prospectsCache = data.map(fromDb);
    return prospectsCache;
  }

  async function loadActions() {
    const { data, error } = await sb
      .from('prospect_actions')
      .select('id, prospect_id, actor_name, action_type, payload, created_at')
      .order('created_at', { ascending: false })
      .limit(30);
    if (error) {
      console.error('[HL] loadActions error', error);
      return [];
    }
    actionsCache = data || [];
    return actionsCache;
  }

  // ── Optimistic write API ──────────────────────────────────────────
  // Mirrors the old loadProspects() / saveProspects(arr) shape.
  function getProspects() { return prospectsCache; }

  function setProspects(arr) {
    // Diff against cache to figure out what changed.
    const oldById = new Map(prospectsCache.map(p => [p.id, p]));
    const newById = new Map(arr.map(p => [p.id, p]));

    // Inserts + updates
    for (const p of arr) {
      const prev = oldById.get(p.id);
      if (!prev || JSON.stringify(prev) !== JSON.stringify(p)) {
        dirty.set(p.id, { type: 'upsert', row: { ...p } });
      }
    }
    // Deletes
    for (const id of oldById.keys()) {
      if (!newById.has(id)) {
        dirty.set(id, { type: 'delete' });
      }
    }
    prospectsCache = arr;
    scheduleFlush();
  }

  function scheduleFlush() {
    if (flushTimer) return;
    flushTimer = setTimeout(flushNow, FLUSH_DEBOUNCE_MS);
  }

  async function flushNow() {
    flushTimer = null;
    if (!dirty.size) return;
    const ops = [...dirty.entries()];
    dirty.clear();

    const upserts = ops.filter(([, v]) => v.type === 'upsert').map(([, v]) => toDb(v.row));
    const deletes = ops.filter(([, v]) => v.type === 'delete').map(([id]) => id);

    if (upserts.length) {
      const { error } = await sb.from('prospects').upsert(upserts, { onConflict: 'id' });
      if (error) console.error('[HL] upsert error', error, upserts.slice(0, 2));
    }
    if (deletes.length) {
      const { error } = await sb.from('prospects').delete().in('id', deletes);
      if (error) console.error('[HL] delete error', error, deletes);
    }
  }

  // ── Action logging ────────────────────────────────────────────────
  async function logAction(prospectId, actorName, actionType, payload) {
    const row = {
      prospect_id: prospectId,
      actor_name: actorName || getActor() || 'unknown',
      action_type: actionType,
      payload: payload || null,
    };
    const { error } = await sb.from('prospect_actions').insert(row);
    if (error) console.error('[HL] logAction error', error, row);
    // Optimistically prepend to local cache so the feed shows it instantly
    actionsCache = [{ ...row, id: Date.now(), created_at: new Date().toISOString() }, ...actionsCache].slice(0, 30);
    if (typeof window.renderActivityFeed === 'function') window.renderActivityFeed();
  }

  // ── Actor identity ────────────────────────────────────────────────
  // No login → ask user once which seller they are; persist locally.
  function getActor() {
    return localStorage.getItem('hl_actor_name') || '';
  }
  function setActor(name) {
    if (!name) localStorage.removeItem('hl_actor_name');
    else localStorage.setItem('hl_actor_name', name);
  }

  // ── Polling ───────────────────────────────────────────────────────
  let pollTimer = null;
  let actionsTimer = null;
  function startPolling() {
    if (pollTimer) return;
    pollTimer = setInterval(async () => {
      // Only refetch if no pending writes (to avoid stomping)
      if (dirty.size) return;
      const fresh = await loadAll();
      // Best-effort merge: if cache shape changed, rerender
      if (fresh.length !== prospectsCache.length || JSON.stringify(fresh) !== JSON.stringify(prospectsCache)) {
        prospectsCache = fresh;
        if (typeof window.renderBoard === 'function') window.renderBoard();
      }
    }, POLL_INTERVAL_MS);
    actionsTimer = setInterval(async () => {
      await loadActions();
      if (typeof window.renderActivityFeed === 'function') window.renderActivityFeed();
    }, ACTIONS_POLL_MS);
  }

  // ── Public API ───────────────────────────────────────────────────
  window.HLDB = {
    boot: async function () {
      await loadAll();
      await loadActions();
      startPolling();
      return prospectsCache;
    },
    getProspects,
    setProspects,
    getActions: () => actionsCache,
    logAction,
    getActor,
    setActor,
    flushNow,
    refresh: async () => { await loadAll(); await loadActions(); },
  };
})();
