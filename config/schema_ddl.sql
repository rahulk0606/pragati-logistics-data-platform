-- ==============================================================================
-- Pragati Enterprises Data Platform - Production Star Schema DDL (5 Tables)
-- Database Engine: MySQL 8.0+
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS pragati_logistics_dw;
USE pragati_logistics_dw;

-- 1. Dimension Table 1: Fleet Vehicles
CREATE TABLE IF NOT EXISTS dim_vehicles (
    vehicle_number VARCHAR(15) PRIMARY KEY,
    fleet_owner_type ENUM('OWNED', 'THIRD_PARTY') NOT NULL,
    carrying_capacity_tons DECIMAL(5,2) NOT NULL
) ENGINE=InnoDB;

-- 2. Dimension Table 2: Material Profile & Density
CREATE TABLE IF NOT EXISTS dim_material_types (
    material_id INT AUTO_INCREMENT PRIMARY KEY,
    material_name VARCHAR(50) NOT NULL UNIQUE,
    density_per_cft DECIMAL(5,2) NOT NULL COMMENT 'Conversion factor for CFT to Metric Tons'
) ENGINE=InnoDB;

-- 3. Dimension Table 3: Crushing Plants & Supply Hubs
CREATE TABLE IF NOT EXISTS dim_hubs (
    hub_id INT AUTO_INCREMENT PRIMARY KEY,
    hub_name VARCHAR(100) NOT NULL,
    state_location VARCHAR(50) NOT NULL
) ENGINE=InnoDB;

-- 4. Dimension Table 4: Multi-State Regulatory Tariffs & Royalties
CREATE TABLE IF NOT EXISTS dim_state_tariffs (
    state_tariff_id INT AUTO_INCREMENT PRIMARY KEY,
    source_state VARCHAR(50) NOT NULL,
    destination_state VARCHAR(50) NOT NULL,
    royalty_per_ton DECIMAL(10,2) NOT NULL,
    state_tax_rate DECIMAL(4,2) NOT NULL COMMENT 'Applicable GST/State Tax Percentage',
    UNIQUE KEY uq_state_route (source_state, destination_state)
) ENGINE=InnoDB;

-- 5. Fact Table: Core Transactional & Billing Ledger
CREATE TABLE IF NOT EXISTS fact_transit_logs (
    transit_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    invoice_number VARCHAR(30) NOT NULL UNIQUE,
    record_date DATE NOT NULL,
    vehicle_number VARCHAR(15) NOT NULL,
    material_id INT NOT NULL,
    hub_id INT NOT NULL,
    state_tariff_id INT NOT NULL,
    raw_volume_cft DECIMAL(10,2) NOT NULL,
    calculated_weight_tons DECIMAL(10,2) NOT NULL,
    base_freight_charges DECIMAL(12,2) NOT NULL,
    final_billing_amount DECIMAL(12,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Strict Foreign Key Constraints across all 4 Dimensions
    CONSTRAINT fk_vehicle FOREIGN KEY (vehicle_number) REFERENCES dim_vehicles(vehicle_number),
    CONSTRAINT fk_material FOREIGN KEY (material_id) REFERENCES dim_material_types(material_id),
    CONSTRAINT fk_hub FOREIGN KEY (hub_id) REFERENCES dim_hubs(hub_id),
    CONSTRAINT fk_tariff FOREIGN KEY (state_tariff_id) REFERENCES dim_state_tariffs(state_tariff_id),
    
    -- Composite Index for High-Speed OLAP Window Analytics
    INDEX idx_fact_dates_tariff (record_date, state_tariff_id)
) ENGINE=InnoDB;

-- ==============================================================================
-- Seed Master Data Across All 4 Dimension Tables
-- ==============================================================================
INSERT IGNORE INTO dim_vehicles (vehicle_number, fleet_owner_type, carrying_capacity_tons) VALUES
('UP14XT1001', 'OWNED', 30.00),
('UP14XT1002', 'OWNED', 30.00),
('HR55AB4510', 'THIRD_PARTY', 25.00),
('RJ14GC8821', 'THIRD_PARTY', 28.00);

INSERT IGNORE INTO dim_material_types (material_id, material_name, density_per_cft) VALUES
(1, 'River Sand', 1.45),
(2, '10mm Crushed Stone', 1.52),
(3, '20mm Concrete Aggregate', 1.55),
(4, '40mm Ballast Stone', 1.50),
(5, 'Stone Dust', 1.38);

INSERT IGNORE INTO dim_hubs (hub_id, hub_name, state_location) VALUES
(1, 'Garhmuktesar Crushing Unit-1', 'Uttar Pradesh'),
(2, 'Hapur Logistics Yard', 'Uttar Pradesh'),
(3, 'Yamunanagar Quarry Hub', 'Haryana'),
(4, 'Kotputli Stone Plant', 'Rajasthan'),
(5, 'Dehradun Foothill Depot', 'Uttarakhand');

INSERT IGNORE INTO dim_state_tariffs (state_tariff_id, source_state, destination_state, royalty_per_ton, state_tax_rate) VALUES
(1, 'Uttar Pradesh', 'Delhi', 120.00, 5.00),
(2, 'Uttar Pradesh', 'Haryana', 110.00, 5.00),
(3, 'Haryana', 'Delhi', 135.00, 5.00),
(4, 'Rajasthan', 'Delhi', 150.00, 5.00),
(5, 'Uttarakhand', 'Uttar Pradesh', 115.00, 5.00),
(6, 'Uttar Pradesh', 'Uttar Pradesh', 85.00, 5.00);
