#!/usr/bin/env python3
"""
Pragati Enterprises - Hybrid Cloud-to-Local ETL Engine (5-Table Star Schema)
Synchronizes all 4 Dimension Tables and loads fact_transit_logs idempotently.
"""

import os
import sys
import argparse
from io import StringIO
from datetime import datetime
import boto3
import pandas as pd
import numpy as np
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "pragati_logistics_dw")
    )

def extract_data(source_mode: str, local_path: str) -> pd.DataFrame:
    if source_mode == "s3":
        bucket = os.getenv("S3_RAW_BUCKET")
        key = os.getenv("S3_DAILY_FEED_KEY", "daily_transit_feed.csv")
        print(f"[EXTRACT] Streaming payload directly into RAM from s3://{bucket}/{key}...")
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "ap-south-1")
        )
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        csv_body = obj['Body'].read().decode('utf-8')
        df = pd.read_csv(StringIO(csv_body))
    else:
        print(f"[EXTRACT] Reading payload from local staging file: {local_path}...")
        df = pd.read_csv(local_path)

    print(f"[EXTRACT] Loaded {len(df):,} raw records into memory.")
    return df

def validate_and_clean(df: pd.DataFrame) -> pd.DataFrame:
    """Drops records missing any of the 4 dimension foreign keys or mandatory invoice IDs."""
    initial_count = len(df)
    required_cols = [
        'invoice_number', 'record_date', 'vehicle_number', 
        'material_id', 'hub_id', 'state_tariff_id', 'raw_volume_cft'
    ]
    df = df.dropna(subset=required_cols)
    df = df[df['raw_volume_cft'] > 0]
    df = df.drop_duplicates(subset=['invoice_number'], keep='last')
    
    dropped = initial_count - len(df)
    if dropped > 0:
        print(f"[QUALITY] Quarantined/dropped {dropped} corrupt or duplicate rows.")
    return df

def sync_and_validate_dimensions(conn, df: pd.DataFrame) -> pd.DataFrame:
    """
    1. Upserts new fleet vehicles into dim_vehicles (Slowly Changing / New Dimension handling).
    2. Validates hub_id, material_id, and state_tariff_id against dim_hubs, dim_material_types, and dim_state_tariffs.
    3. Caches dimension attributes into O(1) lookup dictionaries for transformation.
    """
    print("[DIMENSIONS] Synchronizing and caching all 4 dimension tables...")
    cursor = conn.cursor(dictionary=True)

    # 1. Sync dim_vehicles (Register any new contract trucks automatically)
    unique_vehicles = df['vehicle_number'].unique()
    vehicle_records = [(v, 'THIRD_PARTY', 25.00) for v in unique_vehicles]
    cursor.executemany(
        "INSERT IGNORE INTO dim_vehicles (vehicle_number, fleet_owner_type, carrying_capacity_tons) VALUES (%s, %s, %s)",
        vehicle_records
    )
    conn.commit()

    # 2. Validate against dim_hubs
    cursor.execute("SELECT hub_id FROM dim_hubs")
    valid_hubs = {r['hub_id'] for r in cursor.fetchall()}

    # 3. Cache dim_material_types
    cursor.execute("SELECT material_id, density_per_cft FROM dim_material_types")
    density_map = {r['material_id']: float(r['density_per_cft']) for r in cursor.fetchall()}

    # 4. Cache dim_state_tariffs
    cursor.execute("SELECT state_tariff_id, royalty_per_ton, state_tax_rate FROM dim_state_tariffs")
    tariff_rows = cursor.fetchall()
    royalty_map = {r['state_tariff_id']: float(r['royalty_per_ton']) for r in tariff_rows}
    tax_map = {r['state_tariff_id']: float(r['state_tax_rate']) for r in tariff_rows}
    cursor.close()

    # Enforce Referential Integrity in memory before DB load
    valid_df = df[
        df['hub_id'].isin(valid_hubs) &
        df['material_id'].isin(density_map.keys()) &
        df['state_tariff_id'].isin(royalty_map.keys())
    ].copy()

    # Vectorized Business Calculations using Dimension Lookups
    valid_df['density'] = valid_df['material_id'].map(density_map)
    valid_df['royalty_rate'] = valid_df['state_tariff_id'].map(royalty_map)
    valid_df['tax_rate'] = valid_df['state_tariff_id'].map(tax_map)

    valid_df['calculated_weight_tons'] = np.round((valid_df['raw_volume_cft'] * valid_df['density']) / 20.0, 2)
    royalty_total = valid_df['calculated_weight_tons'] * valid_df['royalty_rate']
    tax_multiplier = 1.0 + (valid_df['tax_rate'] / 100.0)
    valid_df['final_billing_amount'] = np.round((valid_df['base_freight_charges'] + royalty_total) * tax_multiplier, 2)
    valid_df['base_freight_charges'] = np.round(valid_df['base_freight_charges'], 2)

    return valid_df

def load_fact_table_idempotent(conn, df: pd.DataFrame, chunk_size: int = 10000):
    """Commits enriched rows into fact_transit_logs using ON DUPLICATE KEY UPDATE."""
    print(f"[LOAD] Upserting {len(df):,} rows into fact_transit_logs (Batch size: {chunk_size:,})...")
    cursor = conn.cursor()
    
    upsert_sql = """
        INSERT INTO fact_transit_logs (
            invoice_number, record_date, vehicle_number, material_id, 
            hub_id, state_tariff_id, raw_volume_cft, calculated_weight_tons, 
            base_freight_charges, final_billing_amount
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            raw_volume_cft = VALUES(raw_volume_cft),
            calculated_weight_tons = VALUES(calculated_weight_tons),
            base_freight_charges = VALUES(base_freight_charges),
            final_billing_amount = VALUES(final_billing_amount);
    """
    
    cols = [
        'invoice_number', 'record_date', 'vehicle_number', 'material_id',
        'hub_id', 'state_tariff_id', 'raw_volume_cft', 'calculated_weight_tons',
        'base_freight_charges', 'final_billing_amount'
    ]
    records = list(df[cols].itertuples(index=False, name=None))
    
    try:
        for i in range(0, len(records), chunk_size):
            batch = records[i:i + chunk_size]
            cursor.executemany(upsert_sql, batch)
            conn.commit()
            print(f"[LOAD] Committed records {i + 1:,} to {min(i + chunk_size, len(records)):,}")
    except Error as e:
        conn.rollback()
        print(f"[CRITICAL] Transaction failed and rolled back: {str(e)}")
        raise e
    finally:
        cursor.close()

def archive_processed_to_s3(df: pd.DataFrame):
    archive_bucket = os.getenv("S3_ARCHIVE_BUCKET")
    if not archive_bucket:
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_key = f"processed/transit_silver_{timestamp}.csv"
    print(f"[ARCHIVE] Mirroring processed dataset to s3://{archive_bucket}/{archive_key}...")
    
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    
    s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION", "ap-south-1")
    )
    s3_client.put_object(Bucket=archive_bucket, Key=archive_key, Body=csv_buffer.getvalue())
    print("[SUCCESS] Disaster Recovery backup archived to S3 Silver Zone.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pragati Logistics ETL Pipeline")
    parser.add_argument("--source", choices=["local", "s3"], default="local", help="Data extraction source")
    parser.add_argument("--file", type=str, default="data/daily_transit_feed.csv", help="Local file path if source=local")
    parser.add_argument("--archive-s3", action="store_true", help="Archive transformed output back to S3 Silver bucket")
    args = parser.parse_args()

    db_conn = None
    try:
        db_conn = get_db_connection()
        raw_df = extract_data(args.source, args.file)
        clean_df = validate_and_clean(raw_df)
        enriched_df = sync_and_validate_dimensions(db_conn, clean_df)
        load_fact_table_idempotent(db_conn, enriched_df)
        
        if args.archive_s3:
            archive_processed_to_s3(enriched_df)
            
        print("[SUCCESS] End-to-End 5-Table Star Schema Synchronization Completed.")
    except Exception as err:
        print(f"[FATAL] Pipeline execution halted: {str(err)}")
        sys.exit(1)
    finally:
        if db_conn and db_conn.is_connected():
            db_conn.close()
