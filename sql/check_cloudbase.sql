-- 只检查结构和初始化状态，不显示孩子记录、密码或登录盐。
SELECT tablename AS table_name, rowsecurity AS rls_enabled
FROM pg_tables
WHERE schemaname = 'sprout'
ORDER BY tablename;

SELECT
    (SELECT count(*) FROM sprout.state WHERE id = 1) = 1 AS state_ready,
    (SELECT count(*) FROM sprout.login_limit WHERE id = 1) = 1 AS login_limit_ready,
    (SELECT count(*) FROM sprout.auth_config WHERE id = 1 AND octet_length(salt) = 32) = 1 AS auth_config_ready;
