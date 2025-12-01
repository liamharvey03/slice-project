-- Insert a simple test thesis for E4 verification
INSERT INTO thesis (
    id, 
    title, 
    hypothesis, 
    drivers, 
    disconfirmers, 
    expression, 
    start_date, 
    status,
    tags,
    monitor_indices
) VALUES (
    'TEST_T1',
    'Test Gold Long Thesis',
    'Gold will appreciate due to inflation hedging demand',
    '["inflation", "currency debasement"]'::jsonb,
    '["strong USD", "rising real yields"]'::jsonb,
    '[{
        "asset": "GLD",
        "direction": "LONG",
        "size_pct": 100.0
    }]'::jsonb,
    '2024-01-01',
    'ACTIVE',
    '[]'::jsonb,
    '["SPX"]'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title,
    status = EXCLUDED.status;

