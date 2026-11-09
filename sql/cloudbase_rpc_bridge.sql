BEGIN;

GRANT USAGE ON SCHEMA sprout TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
  sprout.state, sprout.revisions, sprout.learning_events,
  sprout.sessions, sprout.login_limit, sprout.auth_config
TO service_role;
GRANT EXECUTE ON FUNCTION
  sprout.bind_http_sql(text, jsonb), sprout.http_bridge(jsonb)
TO service_role;

CREATE OR REPLACE FUNCTION public.sprout_server_bridge(request jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog
AS $body$
BEGIN
  IF (nullif(current_setting('request.jwt.claims', true), '')::jsonb->>'role')
      IS DISTINCT FROM 'service_role' THEN
    RAISE EXCEPTION 'server credential required' USING ERRCODE = '42501';
  END IF;
  RETURN sprout.http_bridge(request);
END;
$body$;

REVOKE ALL ON FUNCTION public.sprout_server_bridge(jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.sprout_server_bridge(jsonb) TO service_role;

COMMIT;

SELECT to_regprocedure('public.sprout_server_bridge(jsonb)') IS NOT NULL AS rpc_bridge_ready;
