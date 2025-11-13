"""
Input validation utilities to prevent injection attacks and ensure data integrity.
"""
from datetime import datetime, timedelta
import re


class InputValidator:
    """Validates user inputs for security and data integrity."""

    @staticmethod
    def validate_date(date_input, allow_future=False):
        """
        Validate and parse date input.

        Args:
            date_input: String in ISO format or datetime object
            allow_future: Whether to allow future dates

        Returns:
            datetime object if valid

        Raises:
            ValueError: If date is invalid
        """
        if isinstance(date_input, datetime):
            date_obj = date_input
        elif isinstance(date_input, str):
            # Validate ISO format (YYYY-MM-DD or full ISO datetime)
            iso_pattern = r'^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?)?$'
            if not re.match(iso_pattern, date_input):
                raise ValueError(f"Invalid date format: {date_input}. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)")

            try:
                date_obj = datetime.fromisoformat(date_input.replace('Z', '+00:00'))
            except ValueError as e:
                raise ValueError(f"Invalid date: {date_input}. {str(e)}")
        else:
            raise ValueError(f"Date must be string or datetime object, got {type(date_input)}")

        # Check if date is too far in the past (before CGM technology existed)
        min_date = datetime(2000, 1, 1)
        if date_obj < min_date:
            raise ValueError(f"Date {date_obj} is before CGM technology existed (2000)")

        # Check if date is in the future
        if not allow_future and date_obj > datetime.now():
            raise ValueError(f"Date {date_obj} is in the future")

        return date_obj

    @staticmethod
    def validate_date_range(start_date, end_date, max_days=365):
        """
        Validate a date range.

        Args:
            start_date: Start date (string or datetime)
            end_date: End date (string or datetime)
            max_days: Maximum allowed range in days

        Returns:
            Tuple of (start_datetime, end_datetime)

        Raises:
            ValueError: If range is invalid
        """
        start = InputValidator.validate_date(start_date)
        end = InputValidator.validate_date(end_date, allow_future=True)

        if start >= end:
            raise ValueError(f"Start date {start} must be before end date {end}")

        range_days = (end - start).days
        if range_days > max_days:
            raise ValueError(f"Date range of {range_days} days exceeds maximum of {max_days} days")

        return start, end

    @staticmethod
    def validate_environment(environment):
        """
        Validate Dexcom environment setting.

        Args:
            environment: Environment string

        Returns:
            Validated environment string

        Raises:
            ValueError: If environment is invalid
        """
        valid_environments = ['sandbox', 'production']
        if environment not in valid_environments:
            raise ValueError(f"Environment must be one of {valid_environments}, got '{environment}'")
        return environment

    @staticmethod
    def validate_days(days):
        """
        Validate days parameter.

        Args:
            days: Number of days (integer)

        Returns:
            Validated days as integer

        Raises:
            ValueError: If days is invalid
        """
        try:
            days_int = int(days)
        except (TypeError, ValueError):
            raise ValueError(f"Days must be an integer, got '{days}'")

        if days_int < 1:
            raise ValueError(f"Days must be positive, got {days_int}")

        if days_int > 365:
            raise ValueError(f"Days must not exceed 365, got {days_int}")

        return days_int

    @staticmethod
    def sanitize_filename(filename):
        """
        Sanitize filename to prevent path traversal attacks.

        Args:
            filename: Proposed filename

        Returns:
            Sanitized filename

        Raises:
            ValueError: If filename is invalid
        """
        if not filename:
            raise ValueError("Filename cannot be empty")

        # Remove any path components
        filename = os.path.basename(filename)

        # Only allow alphanumeric, dash, underscore, and dot
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', filename):
            raise ValueError(f"Filename contains invalid characters: {filename}")

        # Prevent directory traversal
        if '..' in filename or filename.startswith('.'):
            raise ValueError(f"Filename cannot contain '..' or start with '.': {filename}")

        # Validate extension for output files
        valid_extensions = ['.html', '.csv', '.json', '.db']
        ext = os.path.splitext(filename)[1]
        if ext and ext not in valid_extensions:
            raise ValueError(f"File extension {ext} not allowed. Use one of {valid_extensions}")

        return filename


# Add import at top
import os
