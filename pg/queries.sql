WITH CTE AS (
    SELECT 
        *,
        -- Grouping rows by N-minute intervals
        FLOOR(EXTRACT(EPOCH FROM "datetime") / (60 * 60)) AS interval_group,
        LAST_VALUE("close") OVER (
	        PARTITION BY FLOOR(EXTRACT(EPOCH FROM "datetime") / (60 * 60)) 
	        ORDER BY "datetime"
	        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
	    ) AS last_close_in_interval
    FROM stock -- Replace this with your actual table name
    WHERE stock_code = 'NVDA'
)
SELECT
    MIN("datetime") AS start_time,  -- The start time of the N-minute interval
    MAX("datetime") AS end_time,    -- The end time of the N-minute interval
    MIN("low") AS low,              -- Lowest price in the interval
    MAX("high") AS high,            -- Highest price in the interval
    -- Use LAST_VALUE to get the last closing price within the interval
    MAX("last_close_in_interval") AS close, 
    SUM("volume") AS volume         -- Total volume in the interval
FROM CTE
GROUP BY interval_group
ORDER BY start_time;
