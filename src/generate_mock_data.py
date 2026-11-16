#!/usr/bin/env python3
"""
Pragati Enterprises - Production Workload Data Generator
Synthesizes >100,000 realistic transit records and optionally pushes to AWS S3 Bronze Tier.
"""

import os
import sys
import random
import argparse
import boto3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def generate_transit_dataset(output_path: str, record_count: int = 105000) -> str:
    print(f"[GENERATOR] Synthesizing {record_count:,} production transit logs...")
    
    np.random.seed(42)
    random.seed(42)
    
    # 1. Unique Invoice Identifiers
    invoice_numbers = [f"INV-2026-{i:06d}" for i in range(1, record_count + 1)]
    
    # 2. Spread dates across a 90-day Q3/Q4 2026 operational window
    start_date = datetime(2026, 8, 1)
    dates = [start_date + timedelta(days=int(np.random.randint(0, 90))) for _ in range(record_count)]
    dates_str = [d.strftime('%Y-%m-%d') for d in dates]
    
    # 3. Referential Dimension Keys (Aligned with schema_ddl.sql seed values)
    vehicles_pool = [f"UP14XT{random.randint(1000, 9999)}" for _ in range(250)]
    vehicle_numbers = [random.choice(vehicles_pool) for _ in range(record_count)]
    
    material_ids = np.random.randint(1, 6, size=record_count)      # IDs 1 to 5
    hub_ids = np.random.randint(1, 6, size=record_count)           # IDs 1 to 5
    state_tariff_ids = np.random.randint(1, 7, size=record_count)  # IDs 1 to 6
    
    # 4. Continuous Operational Metrics
    raw_volume_cft = np.round(np.random.uniform(250.0, 900.0, size=record_count), 2)
    base_freight_charges = np.round(raw_volume_cft * np.random.uniform(15.00, 28.00, size=record_count), 2)
    
    df = pd.DataFrame({
        'invoice_number': invoice_numbers,
        'record_date': dates_str,
        'vehicle_number': vehicle_numbers,
        'material_id': material_ids,
        'hub_id': hub_ids,
        'state_tariff_id': state_tariff_ids,
        'raw_volume_cft': raw_volume_cft,
        'base_freight_charges': base_freight_charges
    })
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"[SUCCESS] Dataset compiled locally at: {output_path} ({os.path.getsize(output_path) / (1024*1024):.2f} MB)")
    return output_path

def push_to_s3_bronze(local_file_path: str):
    bucket = os.getenv("S3_RAW_BUCKET")
    key = os.getenv("S3_DAILY_FEED_KEY", "daily_transit_feed.csv")
    
    if not bucket:
        print("[WARNING] S3_RAW_BUCKET not configured in .env. Skipping cloud upload.")
        return

    print(f"[AWS S3] Uploading raw batch to s3://{bucket}/{key}...")
    s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION", "ap-south-1")
    )
    s3_client.upload_file(local_file_path, bucket, key)
    print("[SUCCESS] Raw batch safely landed in AWS S3 Bronze Zone.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pragati Logistics Mock Data Generator")
    parser.add_argument("--rows", type=int, default=105000, help="Number of records to generate")
    parser.add_argument("--out", type=str, default="data/daily_transit_feed.csv", help="Local CSV output path")
    parser.add_argument("--upload-s3", action="store_true", help="Upload generated CSV to AWS S3 Bronze bucket")
    args = parser.parse_args()

    generated_path = generate_transit_dataset(args.out, args.rows)
    if args.upload_s3:
        push_to_s3_bronze(generated_path)
