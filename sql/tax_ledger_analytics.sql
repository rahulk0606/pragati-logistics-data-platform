-- ==============================================================================
-- Pragati Enterprises - Production OLAP Star Schema Analytics
-- Joins Fact Table across all 4 Dimension Tables
-- ==============================================================================
USE pragati_logistics_dw;

-- ------------------------------------------------------------------------------
-- QUERY 1: Multi-State Cumulative Tax & Royalty Ledger (Running Total)
-- ------------------------------------------------------------------------------
WITH monthly_route_aggregation AS (
    SELECT 
        DATE_FORMAT(f.record_date, '%Y-%m') AS operational_month,
        CONCAT(t.source_state, ' -> ', t.destination_state) AS state_logistics_route,
        COUNT(f.transit_id) AS total_trips,
        SUM(f.calculated_weight_tons) AS total_tonnage_moved,
        SUM(f.calculated_weight_tons * t.royalty_per_ton) AS total_royalty_collected,
        SUM((f.base_freight_charges + (f.calculated_weight_tons * t.royalty_per_ton)) * (t.state_tax_rate / 100)) AS total_gst_collected,
        SUM(f.final_billing_amount) AS total_gross_revenue
    FROM fact_transit_logs f
    INNER JOIN dim_state_tariffs t ON f.state_tariff_id = t.state_tariff_id
    GROUP BY 1, 2
)
SELECT 
    operational_month,
    state_logistics_route,
    total_trips,
    ROUND(total_tonnage_moved, 2) AS metric_tons,
    ROUND(total_royalty_collected, 2) AS state_royalty_inr,
    ROUND(total_gst_collected, 2) AS gst_liability_inr,
    ROUND(total_gross_revenue, 2) AS monthly_gross_inr,
    ROUND(SUM(total_gross_revenue) OVER (
        PARTITION BY state_logistics_route 
        ORDER BY operational_month 
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ), 2) AS cumulative_route_revenue_inr
FROM monthly_route_aggregation
ORDER BY state_logistics_route, operational_month;


-- ------------------------------------------------------------------------------
-- QUERY 2: Full 5-Table Star Schema Audit (Hub, Material, Fleet & Corridor Yield)
-- ------------------------------------------------------------------------------
WITH star_schema_summary AS (
    SELECT 
        DATE_FORMAT(f.record_date, '%Y-%m') AS operational_month,
        h.hub_name,
        m.material_name,
        v.fleet_owner_type,
        CONCAT(t.source_state, ' -> ', t.destination_state) AS corridor,
        SUM(f.calculated_weight_tons) AS total_tons,
        SUM(f.final_billing_amount) AS gross_revenue
    FROM fact_transit_logs f
    INNER JOIN dim_hubs h ON f.hub_id = h.hub_id
    INNER JOIN dim_material_types m ON f.material_id = m.material_id
    INNER JOIN dim_vehicles v ON f.vehicle_number = v.vehicle_number
    INNER JOIN dim_state_tariffs t ON f.state_tariff_id = t.state_tariff_id
    GROUP BY 1, 2, 3, 4, 5
)
SELECT 
    operational_month,
    hub_name,
    material_name,
    fleet_owner_type,
    corridor,
    ROUND(total_tons, 2) AS total_tons,
    ROUND(gross_revenue, 2) AS gross_revenue_inr,
    DENSE_RANK() OVER (
        PARTITION BY operational_month, hub_name 
        ORDER BY gross_revenue DESC
    ) AS material_revenue_rank_at_hub
FROM star_schema_summary
ORDER BY operational_month, hub_name, material_revenue_rank_at_hub;
