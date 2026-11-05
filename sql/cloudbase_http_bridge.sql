BEGIN;

CREATE OR REPLACE FUNCTION sprout.bind_http_sql(statement text, parameters jsonb)
RETURNS text LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, sprout
AS $body$
DECLARE parts text[]; result text; i integer;
BEGIN
  parts := string_to_array(statement, '?');
  IF array_length(parts, 1) <> jsonb_array_length(parameters) + 1 THEN
    RAISE EXCEPTION 'parameter mismatch';
  END IF;
  result := parts[1];
  FOR i IN 1..jsonb_array_length(parameters) LOOP
    result := result || format('%L', parameters->>(i - 1)) || parts[i + 1];
  END LOOP;
  RETURN result;
END;
$body$;

CREATE OR REPLACE FUNCTION sprout.http_bridge(request jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, sprout
SET lock_timeout = '1500ms'
AS $body$
DECLARE operation jsonb; actual jsonb; statement text;
BEGIN
  IF request->>'action' = 'read' THEN
    statement := sprout.bind_http_sql(request->>'sql', request->'params');
    IF statement !~ '^SELECT ' THEN RAISE EXCEPTION 'read required'; END IF;
    EXECUTE 'SELECT coalesce(jsonb_agg(to_jsonb(q)), ''[]''::jsonb) FROM (' || statement || ') q' INTO actual;
    RETURN jsonb_build_object('rows', actual);
  ELSIF request->>'action' = 'commit' THEN
    PERFORM id FROM sprout.state WHERE id = 1 FOR UPDATE;
    FOR operation IN SELECT value FROM jsonb_array_elements(request->'reads') LOOP
      statement := sprout.bind_http_sql(operation->>'sql', operation->'params');
      IF statement !~ '^SELECT ' THEN RAISE EXCEPTION 'read required'; END IF;
      EXECUTE 'SELECT coalesce(jsonb_agg(to_jsonb(q)), ''[]''::jsonb) FROM (' || statement || ') q' INTO actual;
      IF actual IS DISTINCT FROM operation->'rows' THEN
        RETURN jsonb_build_object('conflict', true);
      END IF;
    END LOOP;
    FOR operation IN SELECT value FROM jsonb_array_elements(request->'writes') LOOP
      statement := sprout.bind_http_sql(operation->>'sql', operation->'params');
      IF statement !~ '^(INSERT|UPDATE|DELETE) ' THEN RAISE EXCEPTION 'write required'; END IF;
      EXECUTE statement;
    END LOOP;
    RETURN jsonb_build_object('ok', true);
  END IF;
  RAISE EXCEPTION 'unknown action';
END;
$body$;

REVOKE ALL ON FUNCTION sprout.bind_http_sql(text, jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION sprout.http_bridge(jsonb) FROM PUBLIC;
COMMIT;

SELECT to_regprocedure('sprout.http_bridge(jsonb)') IS NOT NULL AS http_bridge_ready;
