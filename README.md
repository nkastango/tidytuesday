# Dexcom CGM Data Manager

A comprehensive Python application for downloading, storing, and visualizing your Continuous Glucose Monitoring (CGM) data from Dexcom.

## Features

- **OAuth 2.0 Authentication**: Secure authentication with Dexcom API
- **Data Download**: Fetch historical glucose readings from your Dexcom account
- **Local Storage**: Store data efficiently in DuckDB database
- **Interactive Visualizations**: Create beautiful, interactive charts using Plotly
- **Statistics**: Analyze your glucose patterns and time-in-range metrics

## Project Structure

```
.
├── dexcom_client.py    # Dexcom API client with OAuth authentication
├── database.py         # DuckDB database operations
├── visualize.py        # Plotly visualization functions
├── main.py            # CLI interface
├── requirements.txt   # Python dependencies
├── .env.example       # Example environment configuration
└── README.md         # This file
```

## Prerequisites

- Python 3.8 or higher
- A Dexcom CGM account
- Dexcom Developer API credentials

## Getting Started

### 1. Register for Dexcom API Access

1. Visit [Dexcom Developer Portal](https://developer.dexcom.com/)
2. Create an account or sign in
3. Register a new application
4. Note your `Client ID` and `Client Secret`
5. Set your redirect URI to: `http://localhost:8080/callback`

### 2. Install Dependencies

```bash
# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your credentials
# DEXCOM_CLIENT_ID=your_client_id_here
# DEXCOM_CLIENT_SECRET=your_client_secret_here
# DEXCOM_ENVIRONMENT=sandbox  # Use 'production' for real data
```

### 4. Authenticate

```bash
python main.py auth
```

This will:
- Open your browser for Dexcom login
- Request your authorization
- Store the access token for API requests

## Usage

### Fetch Data

Download your CGM data from Dexcom:

```bash
# Fetch last 7 days (default)
python main.py fetch

# Fetch last 30 days
python main.py fetch --days 30

# Fetch specific date range
python main.py fetch --start-date 2025-01-01 --end-date 2025-01-31

# Include statistics
python main.py fetch --days 30 --include-stats
```

### View Statistics

Display statistics from your stored data:

```bash
# Show stats for last 30 days
python main.py stats --days 30

# Show stats for last 90 days
python main.py stats --days 90
```

Example output:
```
Overall Summary:
  Total readings: 8,640
  Date range: 2024-10-01 to 2025-01-30
  Average glucose: 142.5 mg/dL
  Std deviation: 45.3 mg/dL
  Min/Max: 54 / 289 mg/dL

Time in Range (Last 30 days):
  Very Low (<54 mg/dL):      45 (  0.5%)
  Low (54-70 mg/dL):        234 (  2.7%)
  Target (70-180 mg/dL):  7,823 ( 90.5%)
  High (180-250 mg/dL):     498 (  5.8%)
  Very High (>250 mg/dL):    40 (  0.5%)
```

### Create Visualizations

Generate interactive HTML visualizations:

```bash
# Create comprehensive dashboard
python main.py visualize --type dashboard --days 7

# Create specific visualizations
python main.py visualize --type timeline --days 14
python main.py visualize --type daily --days 30
python main.py visualize --type hourly
python main.py visualize --type time-in-range --days 30

# Create all visualizations
python main.py visualize --type all --days 30
```

Available visualization types:
- **timeline**: Continuous glucose readings over time with target ranges
- **daily**: Daily patterns showing averages, min/max ranges
- **hourly**: Average glucose by hour of day
- **time-in-range**: Pie chart showing percentage of time in different ranges
- **dashboard**: Comprehensive view combining multiple visualizations

### View Visualizations

After creating visualizations, open the generated HTML files in your browser:

```bash
# On macOS
open cgm_dashboard.html

# On Linux
xdg-open cgm_dashboard.html

# On Windows
start cgm_dashboard.html
```

## Data Storage

Data is stored locally in a DuckDB database (`dexcom_data.db` by default). The database contains:

### Tables

1. **glucose_readings**: Individual CGM readings
   - Timestamp (system time and display time)
   - Glucose value (mg/dL)
   - Trend direction and rate
   - Device information

2. **statistics**: Aggregated statistics
   - Time ranges
   - Mean, median, min, max glucose
   - Time in range percentages
   - Coefficient of variation

## Understanding Your Data

### Glucose Ranges

The application uses standard CGM ranges:

| Range | Level | mg/dL |
|-------|-------|-------|
| Very Low | 🔴 | < 54 |
| Low | 🟠 | 54-70 |
| Target | 🟢 | 70-180 |
| High | 🟠 | 180-250 |
| Very High | 🔴 | > 250 |

### Time in Range (TIR)

Time in Range is a key metric for diabetes management. The goal is typically:
- **Target range (70-180 mg/dL)**: >70% of time
- **Below 70 mg/dL**: <4% of time
- **Below 54 mg/dL**: <1% of time
- **Above 180 mg/dL**: <25% of time

## Development

### Running Individual Modules

Each module can be run independently for testing:

```bash
# Test Dexcom API client
python dexcom_client.py

# Test database operations
python database.py

# Test visualizations
python visualize.py
```

### API Rate Limits

Be mindful of Dexcom API rate limits:
- Sandbox: More lenient limits for testing
- Production: Rate limits apply to protect the service

## Troubleshooting

### Authentication Issues

**Problem**: Browser doesn't open for authentication
- **Solution**: Copy the URL from the terminal and paste it into your browser

**Problem**: "Authentication failed" error
- **Solution**: Check your Client ID and Client Secret in `.env`
- **Solution**: Verify your redirect URI matches: `http://localhost:8080/callback`

### Data Issues

**Problem**: "No data available"
- **Solution**: Run `python main.py fetch` to download data first
- **Solution**: Check the date range - you may not have data for the requested period

**Problem**: OAuth token expired
- **Solution**: Run `python main.py auth` to re-authenticate

### Environment Issues

**Problem**: Using sandbox vs production data
- **Solution**: Set `DEXCOM_ENVIRONMENT=production` in `.env` for real data
- **Solution**: Set `DEXCOM_ENVIRONMENT=sandbox` for testing

## Security

This application implements comprehensive security measures to protect your sensitive health data:

### Security Features

✅ **CSRF Protection** - OAuth state parameter validation prevents cross-site request forgery
✅ **Secure Token Storage** - Tokens stored in OS keyring (Keychain/Secret Service/Credential Locker)
✅ **Database Encryption** - Health data encrypted at rest using Fernet (AES-128)
✅ **Input Validation** - All inputs validated to prevent injection attacks
✅ **Secure File Permissions** - Automatic file permission hardening (0600)
✅ **TLS Encryption** - All API communications use HTTPS/TLS 1.2+
✅ **No Logging of Secrets** - Credentials and tokens never logged

### Quick Security Setup

```bash
# Set secure permissions on sensitive files
chmod 600 .env
chmod 600 dexcom_data.db

# Verify .env is not tracked by git
git status --ignored | grep .env

# Check for vulnerable dependencies
pip install safety
safety check
```

### Important Security Notes

- **Never commit `.env`** to version control (already in `.gitignore`)
- **Protect your Client Secret** like a password
- **Use full-disk encryption** for maximum protection
- **OAuth tokens** stored securely in system keyring
- **Database encrypted** automatically with key in keyring
- **Database files** contain PHI - treat as sensitive medical records

For detailed security information, see [SECURITY.md](SECURITY.md)

## Resources

- [Dexcom Developer Portal](https://developer.dexcom.com/)
- [Dexcom API Documentation](https://developer.dexcom.com/docs/)
- [DuckDB Documentation](https://duckdb.org/docs/)
- [Plotly Documentation](https://plotly.com/python/)

## License

This project is for personal use with your own Dexcom data. Ensure compliance with Dexcom's API Terms of Service.

## Contributing

This is a personal project, but feel free to fork and adapt it for your own needs!

## Disclaimer

This software is not affiliated with, endorsed by, or connected to Dexcom, Inc. This is an independent project for personal data management and visualization. Always consult with healthcare professionals for medical decisions.
