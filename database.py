"""
DuckDB database operations for storing Dexcom CGM data with encryption.
"""
import os
import duckdb
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from database_encryption import DataEncryption, set_secure_file_permissions

load_dotenv()


class DexcomDatabase:
    """Database handler for Dexcom CGM data with encryption support."""

    def __init__(self, db_path=None, enable_encryption=True):
        """Initialize database connection with encryption."""
        if db_path is None:
            db_path = os.getenv('DUCKDB_PATH', 'dexcom_data.db')

        self.db_path = db_path
        self.enable_encryption = enable_encryption

        # Initialize encryption if enabled
        self.encryption = DataEncryption() if enable_encryption else None

        # Create database with secure permissions
        is_new_db = not os.path.exists(db_path)
        self.conn = duckdb.connect(db_path)

        # Set secure file permissions on database
        if is_new_db:
            set_secure_file_permissions(db_path)

        self._create_tables()

    def _create_tables(self):
        """Create necessary tables if they don't exist."""
        # Glucose readings table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS glucose_readings (
                record_id VARCHAR PRIMARY KEY,
                system_time TIMESTAMP,
                display_time TIMESTAMP,
                value DOUBLE,
                status VARCHAR,
                trend VARCHAR,
                trend_rate DOUBLE,
                unit VARCHAR,
                rate_unit VARCHAR,
                transmitter_id VARCHAR,
                transmitter_generation VARCHAR,
                display_device VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Statistics table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER PRIMARY KEY,
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                mean_glucose DOUBLE,
                median_glucose DOUBLE,
                min_glucose DOUBLE,
                max_glucose DOUBLE,
                std_deviation DOUBLE,
                time_in_range_very_low DOUBLE,
                time_in_range_low DOUBLE,
                time_in_range_target DOUBLE,
                time_in_range_high DOUBLE,
                time_in_range_very_high DOUBLE,
                coefficient_variation DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for common queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_glucose_display_time
            ON glucose_readings(display_time)
        """)

        print(f"Database initialized at: {self.db_path}")

    def insert_glucose_readings(self, readings):
        """
        Insert glucose readings into the database.

        Args:
            readings: List of glucose reading dicts from Dexcom API

        Returns:
            Number of new records inserted
        """
        if not readings:
            return 0

        # Convert to DataFrame for easier handling
        df = pd.DataFrame(readings)

        # Extract fields
        records = []
        for reading in readings:
            record = {
                'record_id': reading.get('recordId'),
                'system_time': reading.get('systemTime'),
                'display_time': reading.get('displayTime'),
                'value': reading.get('value'),
                'status': reading.get('status'),
                'trend': reading.get('trend'),
                'trend_rate': reading.get('trendRate'),
                'unit': reading.get('unit'),
                'rate_unit': reading.get('rateUnit'),
                'transmitter_id': reading.get('transmitterId'),
                'transmitter_generation': reading.get('transmitterGeneration'),
                'display_device': reading.get('displayDevice')
            }
            records.append(record)

        df = pd.DataFrame(records)

        # Insert with ON CONFLICT DO NOTHING (upsert)
        inserted = 0
        for _, row in df.iterrows():
            try:
                self.conn.execute("""
                    INSERT INTO glucose_readings (
                        record_id, system_time, display_time, value, status,
                        trend, trend_rate, unit, rate_unit, transmitter_id,
                        transmitter_generation, display_device
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT DO NOTHING
                """, row.tolist())
                inserted += 1
            except:
                # Record already exists
                pass

        print(f"Inserted {inserted} new glucose readings")
        return inserted

    def insert_statistics(self, stats, start_date, end_date):
        """
        Insert statistics into the database.

        Args:
            stats: Statistics dict from Dexcom API
            start_date: Start date of statistics period
            end_date: End date of statistics period

        Returns:
            ID of inserted record
        """
        if not stats:
            return None

        # Extract hypoglycemia and hyperglycemia data
        hypo = stats.get('hypoglycemia', {})
        hyper = stats.get('hyperglycemia', {})
        target = stats.get('targetRange', {})

        result = self.conn.execute("""
            INSERT INTO statistics (
                start_date, end_date, mean_glucose, median_glucose,
                min_glucose, max_glucose, std_deviation,
                time_in_range_very_low, time_in_range_low,
                time_in_range_target, time_in_range_high,
                time_in_range_very_high, coefficient_variation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
        """, [
            start_date,
            end_date,
            stats.get('mean'),
            stats.get('median'),
            stats.get('min'),
            stats.get('max'),
            stats.get('stdDev'),
            hypo.get('veryLow'),
            hypo.get('low'),
            target.get('target'),
            hyper.get('high'),
            hyper.get('veryHigh'),
            stats.get('coefficientVariation')
        ])

        record_id = result.fetchone()[0]
        print(f"Inserted statistics record with ID: {record_id}")
        return record_id

    def get_glucose_readings(self, start_date=None, end_date=None, limit=None):
        """
        Retrieve glucose readings from the database.

        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Optional limit on number of records

        Returns:
            Pandas DataFrame of glucose readings
        """
        query = "SELECT * FROM glucose_readings"
        conditions = []
        params = []

        if start_date:
            conditions.append("display_time >= ?")
            params.append(start_date)

        if end_date:
            conditions.append("display_time <= ?")
            params.append(end_date)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY display_time DESC"

        if limit:
            query += f" LIMIT {limit}"

        return self.conn.execute(query, params).df()

    def get_statistics(self, start_date=None, end_date=None):
        """
        Retrieve statistics from the database.

        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Pandas DataFrame of statistics
        """
        query = "SELECT * FROM statistics"
        conditions = []
        params = []

        if start_date:
            conditions.append("start_date >= ?")
            params.append(start_date)

        if end_date:
            conditions.append("end_date <= ?")
            params.append(end_date)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY start_date DESC"

        return self.conn.execute(query, params).df()

    def get_summary_stats(self):
        """Get summary statistics from stored data."""
        query = """
            SELECT
                COUNT(*) as total_readings,
                MIN(display_time) as earliest_reading,
                MAX(display_time) as latest_reading,
                AVG(value) as avg_glucose,
                MIN(value) as min_glucose,
                MAX(value) as max_glucose,
                STDDEV(value) as std_glucose
            FROM glucose_readings
            WHERE status IS NULL OR status != 'outlier'
        """
        return self.conn.execute(query).df()

    def get_daily_stats(self, days=30):
        """
        Get daily statistics for the last N days.

        Args:
            days: Number of days to analyze

        Returns:
            Pandas DataFrame with daily statistics
        """
        query = """
            SELECT
                DATE_TRUNC('day', display_time) as date,
                COUNT(*) as num_readings,
                AVG(value) as avg_glucose,
                MIN(value) as min_glucose,
                MAX(value) as max_glucose,
                STDDEV(value) as std_glucose,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value) as median_glucose
            FROM glucose_readings
            WHERE display_time >= CURRENT_TIMESTAMP - INTERVAL ? DAYS
                AND (status IS NULL OR status != 'outlier')
            GROUP BY DATE_TRUNC('day', display_time)
            ORDER BY date DESC
        """
        return self.conn.execute(query, [days]).df()

    def get_hourly_patterns(self):
        """Get average glucose by hour of day."""
        query = """
            SELECT
                EXTRACT(HOUR FROM display_time) as hour,
                COUNT(*) as num_readings,
                AVG(value) as avg_glucose,
                STDDEV(value) as std_glucose
            FROM glucose_readings
            WHERE status IS NULL OR status != 'outlier'
            GROUP BY EXTRACT(HOUR FROM display_time)
            ORDER BY hour
        """
        return self.conn.execute(query).df()

    def close(self):
        """Close database connection."""
        self.conn.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


if __name__ == "__main__":
    # Example usage
    db = DexcomDatabase()

    # Get summary statistics
    summary = db.get_summary_stats()
    print("\nDatabase Summary:")
    print(summary)

    # Get recent readings
    recent = db.get_glucose_readings(limit=10)
    print(f"\nLast 10 readings:")
    print(recent[['display_time', 'value', 'trend']] if not recent.empty else "No data")

    db.close()
