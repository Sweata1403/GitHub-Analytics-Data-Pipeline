-- ============================================================
-- Seed dim_date: Generate calendar dimension from 2020 to 2030
-- ============================================================
-- Run this after schema.sql to populate the date dimension.
-- ============================================================

INSERT INTO dim_date (
    date_id,
    full_date,
    year,
    quarter,
    month,
    month_name,
    week,
    day_of_month,
    day_of_week,
    day_name,
    is_weekend
)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INTEGER                         AS date_id,
    d::DATE                                                   AS full_date,
    EXTRACT(YEAR FROM d)::SMALLINT                           AS year,
    EXTRACT(QUARTER FROM d)::SMALLINT                        AS quarter,
    EXTRACT(MONTH FROM d)::SMALLINT                          AS month,
    TO_CHAR(d, 'Month')                                      AS month_name,
    EXTRACT(WEEK FROM d)::SMALLINT                           AS week,
    EXTRACT(DAY FROM d)::SMALLINT                            AS day_of_month,
    EXTRACT(ISODOW FROM d)::SMALLINT - 1                     AS day_of_week,   -- 0=Mon
    TO_CHAR(d, 'Day')                                        AS day_name,
    EXTRACT(ISODOW FROM d) IN (6, 7)                         AS is_weekend
FROM generate_series(
    '2020-01-01'::DATE,
    '2030-12-31'::DATE,
    '1 day'::INTERVAL
) AS d
ON CONFLICT (date_id) DO NOTHING;

-- Verify
-- SELECT COUNT(*) FROM dim_date;  -- Should be 4,018 rows
