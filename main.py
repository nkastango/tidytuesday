#!/usr/bin/env python3
"""
Main CLI for downloading, storing, and visualizing Dexcom CGM data.
"""
import argparse
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

from dexcom_client import DexcomClient
from database import DexcomDatabase
from visualize import CGMVisualizer

load_dotenv()


def authenticate_command(args):
    """Authenticate with Dexcom API."""
    print("=== Dexcom Authentication ===\n")

    environment = os.getenv('DEXCOM_ENVIRONMENT', 'sandbox')
    print(f"Environment: {environment}")

    client = DexcomClient(environment=environment)

    try:
        client.authenticate()
        print("\n✓ Authentication successful!")
        print("\nYou can now use the 'fetch' command to download your data.")
    except Exception as e:
        print(f"\n✗ Authentication failed: {e}")
        sys.exit(1)


def fetch_command(args):
    """Fetch data from Dexcom API and store in database."""
    print("=== Fetching Dexcom Data ===\n")

    environment = os.getenv('DEXCOM_ENVIRONMENT', 'sandbox')
    client = DexcomClient(environment=environment)
    db = DexcomDatabase()

    try:
        # Authenticate
        print("Authenticating...")
        client.authenticate()

        # Determine date range
        if args.days:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=args.days)
            print(f"\nFetching last {args.days} days of data...")
        elif args.start_date and args.end_date:
            start_date = datetime.fromisoformat(args.start_date)
            end_date = datetime.fromisoformat(args.end_date)
            print(f"\nFetching data from {start_date} to {end_date}...")
        else:
            # Get available data range
            data_range = client.get_data_range()
            if data_range:
                print(f"\nAvailable data range:")
                print(f"  Start: {data_range.get('start', {}).get('systemTime', 'N/A')}")
                print(f"  End: {data_range.get('end', {}).get('systemTime', 'N/A')}")

            # Default to last 7 days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            print(f"\nFetching last 7 days of data...")

        # Fetch glucose readings
        print("\nDownloading glucose readings...")
        readings = client.get_glucose_readings(start_date, end_date)
        print(f"Downloaded {len(readings)} readings")

        # Store in database
        if readings:
            print("\nStoring data in database...")
            inserted = db.insert_glucose_readings(readings)
            print(f"Stored {inserted} new readings")

        # Fetch and store statistics
        if args.include_stats:
            print("\nDownloading statistics...")
            stats = client.get_statistics(start_date, end_date)
            if stats:
                db.insert_statistics(stats, start_date, end_date)
                print("✓ Statistics stored")

        # Show summary
        print("\n=== Database Summary ===")
        summary = db.get_summary_stats()
        if not summary.empty:
            print(f"Total readings: {summary['total_readings'].iloc[0]}")
            print(f"Date range: {summary['earliest_reading'].iloc[0]} to {summary['latest_reading'].iloc[0]}")
            print(f"Average glucose: {summary['avg_glucose'].iloc[0]:.1f} mg/dL")
            print(f"Range: {summary['min_glucose'].iloc[0]:.0f} - {summary['max_glucose'].iloc[0]:.0f} mg/dL")

        print("\n✓ Data fetch complete!")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


def visualize_command(args):
    """Create visualizations from stored data."""
    print("=== Creating Visualizations ===\n")

    viz = CGMVisualizer()

    try:
        if args.type == 'timeline' or args.type == 'all':
            print("Creating glucose timeline...")
            fig = viz.create_glucose_timeline(days=args.days)
            if fig:
                filename = args.output or 'glucose_timeline.html'
                viz.save_figure(fig, filename)

        if args.type == 'daily' or args.type == 'all':
            print("Creating daily patterns...")
            fig = viz.create_daily_patterns(days=args.days)
            if fig:
                filename = args.output or 'daily_patterns.html'
                viz.save_figure(fig, filename)

        if args.type == 'hourly' or args.type == 'all':
            print("Creating hourly patterns...")
            fig = viz.create_hourly_patterns()
            if fig:
                filename = args.output or 'hourly_patterns.html'
                viz.save_figure(fig, filename)

        if args.type == 'time-in-range' or args.type == 'all':
            print("Creating time in range chart...")
            fig = viz.create_time_in_range_chart(days=args.days)
            if fig:
                filename = args.output or 'time_in_range.html'
                viz.save_figure(fig, filename)

        if args.type == 'dashboard':
            print("Creating comprehensive dashboard...")
            fig = viz.create_dashboard(days=args.days)
            if fig:
                filename = args.output or 'cgm_dashboard.html'
                viz.save_figure(fig, filename)

        print("\n✓ Visualizations created!")
        print("\nOpen the HTML files in your browser to view them.")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def stats_command(args):
    """Show statistics from stored data."""
    print("=== CGM Data Statistics ===\n")

    db = DexcomDatabase()

    try:
        # Overall summary
        summary = db.get_summary_stats()
        if not summary.empty:
            print("Overall Summary:")
            print(f"  Total readings: {summary['total_readings'].iloc[0]:,}")
            print(f"  Date range: {summary['earliest_reading'].iloc[0]} to {summary['latest_reading'].iloc[0]}")
            print(f"  Average glucose: {summary['avg_glucose'].iloc[0]:.1f} mg/dL")
            print(f"  Std deviation: {summary['std_glucose'].iloc[0]:.1f} mg/dL")
            print(f"  Min/Max: {summary['min_glucose'].iloc[0]:.0f} / {summary['max_glucose'].iloc[0]:.0f} mg/dL")
        else:
            print("No data available. Run 'fetch' command first.")
            return

        # Recent daily stats
        print(f"\n\nDaily Statistics (Last {args.days} days):")
        daily = db.get_daily_stats(days=args.days)
        if not daily.empty:
            print(f"\n{'Date':<12} {'Readings':>10} {'Avg':>8} {'Min':>8} {'Max':>8} {'StdDev':>8}")
            print("-" * 68)
            for _, row in daily.iterrows():
                date_str = row['date'].strftime('%Y-%m-%d')
                print(f"{date_str:<12} {row['num_readings']:>10.0f} {row['avg_glucose']:>8.1f} "
                      f"{row['min_glucose']:>8.0f} {row['max_glucose']:>8.0f} {row['std_glucose']:>8.1f}")

        # Time in range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days)
        readings = db.get_glucose_readings(start_date, end_date)

        if not readings.empty:
            print(f"\n\nTime in Range (Last {args.days} days):")
            total = len(readings)
            very_low = len(readings[readings['value'] < 54])
            low = len(readings[(readings['value'] >= 54) & (readings['value'] < 70)])
            target = len(readings[(readings['value'] >= 70) & (readings['value'] <= 180)])
            high = len(readings[(readings['value'] > 180) & (readings['value'] <= 250)])
            very_high = len(readings[readings['value'] > 250])

            print(f"  Very Low (<54 mg/dL):    {very_low:5d} ({very_low/total*100:5.1f}%)")
            print(f"  Low (54-70 mg/dL):       {low:5d} ({low/total*100:5.1f}%)")
            print(f"  Target (70-180 mg/dL):   {target:5d} ({target/total*100:5.1f}%)")
            print(f"  High (180-250 mg/dL):    {high:5d} ({high/total*100:5.1f}%)")
            print(f"  Very High (>250 mg/dL):  {very_high:5d} ({very_high/total*100:5.1f}%)")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Dexcom CGM Data Manager - Download, store, and visualize your continuous glucose monitoring data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # First-time setup: authenticate with Dexcom
  python main.py auth

  # Fetch last 30 days of data
  python main.py fetch --days 30

  # Fetch data for specific date range
  python main.py fetch --start-date 2025-01-01 --end-date 2025-01-31

  # View statistics
  python main.py stats --days 30

  # Create dashboard visualization
  python main.py visualize --type dashboard --days 7

  # Create specific visualizations
  python main.py visualize --type timeline --days 14
  python main.py visualize --type daily --days 30
  python main.py visualize --type hourly
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Auth command
    auth_parser = subparsers.add_parser('auth', help='Authenticate with Dexcom API')

    # Fetch command
    fetch_parser = subparsers.add_parser('fetch', help='Fetch data from Dexcom')
    fetch_parser.add_argument('--days', type=int, help='Number of days to fetch (default: 7)')
    fetch_parser.add_argument('--start-date', help='Start date (ISO format: YYYY-MM-DD)')
    fetch_parser.add_argument('--end-date', help='End date (ISO format: YYYY-MM-DD)')
    fetch_parser.add_argument('--include-stats', action='store_true', help='Also fetch statistics')

    # Visualize command
    viz_parser = subparsers.add_parser('visualize', help='Create visualizations')
    viz_parser.add_argument('--type', choices=['timeline', 'daily', 'hourly', 'time-in-range', 'dashboard', 'all'],
                           default='dashboard', help='Type of visualization')
    viz_parser.add_argument('--days', type=int, default=7, help='Number of days to visualize')
    viz_parser.add_argument('--output', help='Output filename')

    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show statistics from stored data')
    stats_parser.add_argument('--days', type=int, default=30, help='Number of days for statistics')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Check for .env file
    if not os.path.exists('.env') and args.command != 'stats':
        print("⚠ Warning: .env file not found!")
        print("\nPlease create a .env file with your Dexcom API credentials.")
        print("You can copy .env.example to .env and fill in your credentials:")
        print("  cp .env.example .env")
        print("\nGet API credentials from: https://developer.dexcom.com/")
        sys.exit(1)

    # Route to appropriate command handler
    if args.command == 'auth':
        authenticate_command(args)
    elif args.command == 'fetch':
        fetch_command(args)
    elif args.command == 'visualize':
        visualize_command(args)
    elif args.command == 'stats':
        stats_command(args)


if __name__ == "__main__":
    main()
