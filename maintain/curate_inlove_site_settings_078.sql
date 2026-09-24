-- DB-1 (change 078): tenant-scoped, idempotent local correction of `contacts.*`
-- site_settings entries for tenant `inlove`.
--
-- Scope (design.md D3-D6, spec `inlove-site-settings-curation`):
--   1. Split `contacts.coordinates` (type=object JSON {latitude,longitude}) into
--      `contacts.map.latitude` and `contacts.map.longitude` (type=float), then
--      remove `contacts.coordinates`.
--   2. Rename `contacts.maps_url` -> `contacts.map.url` (same type/value).
--   3. Fix `contacts.nearest_stop`: type=object JSON {name,distance_m,...} ->
--      type=string, single human-readable line built from name + distance_m.
--   4. Delete `contacts.working_hours` (superseded by contacts.hours.* below).
--   5. Add/upsert `contacts.hours.weekdays.start/stop` and
--      `contacts.hours.weekend.start/stop` (type=time, HH:MM).
--
-- This script touches ONLY the resolved tenant `inlove` equestrian_id and is
-- safe to run multiple times: the second run performs zero inserts/deletes
-- (verified via row-count diffing in db-1-evidence.md). It does not use
-- Alembic and must never be pointed at a non-local database.
--
-- Usage: psql -v ON_ERROR_STOP=1 -f curate_inlove_site_settings_078.sql <local db>

BEGIN;

DO $migration$
DECLARE
    v_equestrian_id uuid;
BEGIN
    -- Abort guard: resolve tenant strictly, fail loudly if selector is missing
    -- or ambiguous instead of silently touching zero/wrong rows.
    SELECT id INTO STRICT v_equestrian_id
      FROM equestrians
     WHERE service_key = 'inlove';

    -- (1) contacts.coordinates -> contacts.map.latitude / contacts.map.longitude
    -- Delete-then-insert in one data-modifying CTE: avoids a transient
    -- (equestrian_id, name) collision between the old and new rows (both would
    -- otherwise briefly share a human-readable name), and is naturally
    -- idempotent (second run: nothing to delete, CTE empty, INSERT is a no-op).
    WITH removed AS (
        DELETE FROM site_settings
         WHERE equestrian_id = v_equestrian_id
           AND key = 'contacts.coordinates'
           AND type = 'object'
        RETURNING value
    ),
    split AS (
        SELECT 'contacts.map.latitude' AS key,
               (removed.value::jsonb ->> 'latitude') AS value,
               'Широта клуба' AS name
          FROM removed
        UNION ALL
        SELECT 'contacts.map.longitude',
               (removed.value::jsonb ->> 'longitude'),
               'Долгота клуба'
          FROM removed
    )
    INSERT INTO site_settings (id, created_at, updated_at, equestrian_id, key, value, name, type)
    SELECT gen_random_uuid(), now(), NULL, v_equestrian_id, split.key, split.value, split.name, 'float'
      FROM split
    ON CONFLICT (equestrian_id, key) DO UPDATE
       SET value = EXCLUDED.value, type = EXCLUDED.type, updated_at = now()
     WHERE site_settings.value IS DISTINCT FROM EXCLUDED.value
        OR site_settings.type IS DISTINCT FROM EXCLUDED.type;

    -- (2) contacts.maps_url -> contacts.map.url (rename, same value/type)
    WITH removed AS (
        DELETE FROM site_settings
         WHERE equestrian_id = v_equestrian_id
           AND key = 'contacts.maps_url'
        RETURNING value, type
    )
    INSERT INTO site_settings (id, created_at, updated_at, equestrian_id, key, value, name, type)
    SELECT gen_random_uuid(), now(), NULL, v_equestrian_id,
           'contacts.map.url', removed.value, 'Ссылка на карту', removed.type
      FROM removed
    ON CONFLICT (equestrian_id, key) DO UPDATE
       SET value = EXCLUDED.value, type = EXCLUDED.type, updated_at = now()
     WHERE site_settings.value IS DISTINCT FROM EXCLUDED.value
        OR site_settings.type IS DISTINCT FROM EXCLUDED.type;

    -- (3) contacts.nearest_stop: object JSON -> readable string (only while
    -- still stored as object; already-corrected rows are left untouched, making
    -- this idempotent).
    UPDATE site_settings
       SET value = format(
             '%s, ≈%s км',
             (value::jsonb ->> 'name'),
             round(((value::jsonb ->> 'distance_m')::numeric) / 1000.0)::int
           ),
           type = 'string',
           updated_at = now()
     WHERE equestrian_id = v_equestrian_id
       AND key = 'contacts.nearest_stop'
       AND type = 'object';

    -- (4) contacts.working_hours: removed without replacement/alias.
    DELETE FROM site_settings
     WHERE equestrian_id = v_equestrian_id
       AND key = 'contacts.working_hours';

    -- (5) contacts.hours.* — four new time settings (idempotent upsert).
    INSERT INTO site_settings (id, created_at, updated_at, equestrian_id, key, value, name, type)
    VALUES
      (gen_random_uuid(), now(), NULL, v_equestrian_id, 'contacts.hours.weekdays.start', '10:00', 'Будни: начало работы', 'time'),
      (gen_random_uuid(), now(), NULL, v_equestrian_id, 'contacts.hours.weekdays.stop', '21:00', 'Будни: окончание работы', 'time'),
      (gen_random_uuid(), now(), NULL, v_equestrian_id, 'contacts.hours.weekend.start', '10:00', 'Выходные: начало работы', 'time'),
      (gen_random_uuid(), now(), NULL, v_equestrian_id, 'contacts.hours.weekend.stop', '21:00', 'Выходные: окончание работы', 'time')
    ON CONFLICT (equestrian_id, key) DO UPDATE
       SET value = EXCLUDED.value, type = EXCLUDED.type, updated_at = now()
     WHERE site_settings.value IS DISTINCT FROM EXCLUDED.value
        OR site_settings.type IS DISTINCT FROM EXCLUDED.type;
END
$migration$;

COMMIT;
