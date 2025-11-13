"""
Visualization module for Dexcom CGM data.
Creates interactive charts using Plotly.
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta
from database import DexcomDatabase


class CGMVisualizer:
    """Create visualizations for CGM data."""

    # Standard glucose ranges (mg/dL)
    RANGES = {
        'very_low': (0, 54),
        'low': (54, 70),
        'target': (70, 180),
        'high': (180, 250),
        'very_high': (250, 400)
    }

    COLORS = {
        'very_low': '#d32f2f',  # Red
        'low': '#f57c00',       # Orange
        'target': '#388e3c',    # Green
        'high': '#f57c00',      # Orange
        'very_high': '#d32f2f', # Red
        'reading': '#1976d2'    # Blue
    }

    def __init__(self, db_path=None):
        """Initialize visualizer with database connection."""
        self.db = DexcomDatabase(db_path)

    def create_glucose_timeline(self, start_date=None, end_date=None, days=7):
        """
        Create an interactive timeline of glucose readings.

        Args:
            start_date: Start date for data (optional)
            end_date: End date for data (optional)
            days: Number of days to show if dates not specified

        Returns:
            Plotly figure object
        """
        if not start_date and not end_date:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

        df = self.db.get_glucose_readings(start_date, end_date)

        if df.empty:
            print("No data available for the specified date range")
            return None

        # Convert timestamps to datetime
        df['display_time'] = pd.to_datetime(df['display_time'])

        # Create figure
        fig = go.Figure()

        # Add glucose readings line
        fig.add_trace(go.Scatter(
            x=df['display_time'],
            y=df['value'],
            mode='lines+markers',
            name='Glucose',
            line=dict(color=self.COLORS['reading'], width=2),
            marker=dict(size=4),
            hovertemplate='<b>%{y:.0f} mg/dL</b><br>%{x}<br>Trend: %{customdata}<extra></extra>',
            customdata=df['trend']
        ))

        # Add target range
        fig.add_hrect(
            y0=self.RANGES['target'][0], y1=self.RANGES['target'][1],
            fillcolor=self.COLORS['target'], opacity=0.1,
            layer="below", line_width=0,
            annotation_text="Target Range", annotation_position="left"
        )

        # Add low range
        fig.add_hrect(
            y0=self.RANGES['low'][0], y1=self.RANGES['low'][1],
            fillcolor=self.COLORS['low'], opacity=0.1,
            layer="below", line_width=0
        )

        # Add very low range
        fig.add_hrect(
            y0=self.RANGES['very_low'][0], y1=self.RANGES['very_low'][1],
            fillcolor=self.COLORS['very_low'], opacity=0.1,
            layer="below", line_width=0
        )

        # Add high range
        fig.add_hrect(
            y0=self.RANGES['high'][0], y1=self.RANGES['high'][1],
            fillcolor=self.COLORS['high'], opacity=0.1,
            layer="below", line_width=0
        )

        # Add very high range
        fig.add_hrect(
            y0=self.RANGES['very_high'][0], y1=self.RANGES['very_high'][1],
            fillcolor=self.COLORS['very_high'], opacity=0.1,
            layer="below", line_width=0
        )

        # Update layout
        fig.update_layout(
            title='Continuous Glucose Monitor - Timeline View',
            xaxis_title='Time',
            yaxis_title='Glucose (mg/dL)',
            hovermode='closest',
            height=600,
            showlegend=True,
            yaxis=dict(range=[40, 400])
        )

        return fig

    def create_daily_patterns(self, days=30):
        """
        Create visualization of daily patterns.

        Args:
            days: Number of days to analyze

        Returns:
            Plotly figure object
        """
        df = self.db.get_daily_stats(days)

        if df.empty:
            print("No data available for daily patterns")
            return None

        # Convert date column
        df['date'] = pd.to_datetime(df['date'])

        # Create figure with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Add average glucose
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['avg_glucose'],
                mode='lines+markers',
                name='Daily Average',
                line=dict(color='#1976d2', width=2),
                marker=dict(size=8)
            ),
            secondary_y=False,
        )

        # Add min/max range
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['max_glucose'],
                mode='lines',
                name='Max',
                line=dict(color='#d32f2f', width=1, dash='dash'),
                showlegend=True
            ),
            secondary_y=False,
        )

        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['min_glucose'],
                mode='lines',
                name='Min',
                line=dict(color='#388e3c', width=1, dash='dash'),
                showlegend=True
            ),
            secondary_y=False,
        )

        # Add number of readings
        fig.add_trace(
            go.Bar(
                x=df['date'],
                y=df['num_readings'],
                name='# Readings',
                marker_color='lightblue',
                opacity=0.3
            ),
            secondary_y=True,
        )

        # Add target range reference lines
        fig.add_hline(y=70, line_dash="dot", line_color="green", opacity=0.5, secondary_y=False)
        fig.add_hline(y=180, line_dash="dot", line_color="green", opacity=0.5, secondary_y=False)

        # Update layout
        fig.update_xaxes(title_text="Date")
        fig.update_yaxes(title_text="Glucose (mg/dL)", secondary_y=False)
        fig.update_yaxes(title_text="Number of Readings", secondary_y=True)

        fig.update_layout(
            title=f'Daily Glucose Patterns (Last {days} Days)',
            hovermode='x unified',
            height=600
        )

        return fig

    def create_hourly_patterns(self):
        """
        Create visualization of hourly patterns (average by time of day).

        Returns:
            Plotly figure object
        """
        df = self.db.get_hourly_patterns()

        if df.empty:
            print("No data available for hourly patterns")
            return None

        # Create figure
        fig = go.Figure()

        # Add average glucose by hour
        fig.add_trace(go.Scatter(
            x=df['hour'],
            y=df['avg_glucose'],
            mode='lines+markers',
            name='Average Glucose',
            line=dict(color='#1976d2', width=3),
            marker=dict(size=10),
            fill='tonexty'
        ))

        # Add standard deviation bands
        upper_band = df['avg_glucose'] + df['std_glucose']
        lower_band = df['avg_glucose'] - df['std_glucose']

        fig.add_trace(go.Scatter(
            x=df['hour'],
            y=upper_band,
            mode='lines',
            name='+1 SD',
            line=dict(color='lightblue', width=1, dash='dash'),
            showlegend=False
        ))

        fig.add_trace(go.Scatter(
            x=df['hour'],
            y=lower_band,
            mode='lines',
            name='-1 SD',
            line=dict(color='lightblue', width=1, dash='dash'),
            fill='tonexty',
            fillcolor='rgba(173, 216, 230, 0.2)',
            showlegend=False
        ))

        # Add target range reference lines
        fig.add_hline(y=70, line_dash="dot", line_color="green", opacity=0.5, annotation_text="Target Low")
        fig.add_hline(y=180, line_dash="dot", line_color="green", opacity=0.5, annotation_text="Target High")

        # Update layout
        fig.update_layout(
            title='Average Glucose by Hour of Day',
            xaxis_title='Hour of Day',
            yaxis_title='Glucose (mg/dL)',
            xaxis=dict(tickmode='linear', tick0=0, dtick=2),
            height=600,
            hovermode='x unified'
        )

        return fig

    def create_time_in_range_chart(self, days=30):
        """
        Create a pie chart showing time in different glucose ranges.

        Args:
            days: Number of days to analyze

        Returns:
            Plotly figure object
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        df = self.db.get_glucose_readings(start_date, end_date)

        if df.empty:
            print("No data available for time in range")
            return None

        # Calculate time in each range
        counts = {
            'Very Low (<54)': len(df[df['value'] < 54]),
            'Low (54-70)': len(df[(df['value'] >= 54) & (df['value'] < 70)]),
            'Target (70-180)': len(df[(df['value'] >= 70) & (df['value'] <= 180)]),
            'High (180-250)': len(df[(df['value'] > 180) & (df['value'] <= 250)]),
            'Very High (>250)': len(df[df['value'] > 250])
        }

        colors = [
            self.COLORS['very_low'],
            self.COLORS['low'],
            self.COLORS['target'],
            self.COLORS['high'],
            self.COLORS['very_high']
        ]

        fig = go.Figure(data=[go.Pie(
            labels=list(counts.keys()),
            values=list(counts.values()),
            marker=dict(colors=colors),
            textinfo='label+percent',
            hovertemplate='<b>%{label}</b><br>%{value} readings<br>%{percent}<extra></extra>'
        )])

        fig.update_layout(
            title=f'Time in Range (Last {days} Days)',
            height=600
        )

        return fig

    def create_dashboard(self, days=7):
        """
        Create a comprehensive dashboard with multiple visualizations.

        Args:
            days: Number of days to show in timeline

        Returns:
            Plotly figure object
        """
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Glucose Timeline', 'Time in Range', 'Daily Patterns', 'Hourly Patterns'),
            specs=[
                [{"type": "scatter", "colspan": 2}, None],
                [{"type": "pie"}, {"type": "scatter"}]
            ],
            vertical_spacing=0.15,
            horizontal_spacing=0.1
        )

        # Get data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        readings_df = self.db.get_glucose_readings(start_date, end_date)
        hourly_df = self.db.get_hourly_patterns()

        if not readings_df.empty:
            readings_df['display_time'] = pd.to_datetime(readings_df['display_time'])

            # 1. Glucose Timeline (row 1, spans both columns)
            fig.add_trace(
                go.Scatter(
                    x=readings_df['display_time'],
                    y=readings_df['value'],
                    mode='lines+markers',
                    name='Glucose',
                    line=dict(color=self.COLORS['reading'], width=2),
                    marker=dict(size=3)
                ),
                row=1, col=1
            )

            # 2. Time in Range Pie Chart (row 2, col 1)
            counts = {
                'Very Low': len(readings_df[readings_df['value'] < 54]),
                'Low': len(readings_df[(readings_df['value'] >= 54) & (readings_df['value'] < 70)]),
                'Target': len(readings_df[(readings_df['value'] >= 70) & (readings_df['value'] <= 180)]),
                'High': len(readings_df[(readings_df['value'] > 180) & (readings_df['value'] <= 250)]),
                'Very High': len(readings_df[readings_df['value'] > 250])
            }

            fig.add_trace(
                go.Pie(
                    labels=list(counts.keys()),
                    values=list(counts.values()),
                    marker=dict(colors=[
                        self.COLORS['very_low'], self.COLORS['low'],
                        self.COLORS['target'], self.COLORS['high'],
                        self.COLORS['very_high']
                    ]),
                    showlegend=False
                ),
                row=2, col=1
            )

        # 3. Hourly Patterns (row 2, col 2)
        if not hourly_df.empty:
            fig.add_trace(
                go.Scatter(
                    x=hourly_df['hour'],
                    y=hourly_df['avg_glucose'],
                    mode='lines+markers',
                    name='Hourly Avg',
                    line=dict(color='#1976d2', width=2),
                    marker=dict(size=6)
                ),
                row=2, col=2
            )

        # Update layout
        fig.update_layout(
            title_text=f'CGM Dashboard (Last {days} Days)',
            height=900,
            showlegend=True
        )

        # Update y-axes for glucose charts
        fig.update_yaxes(title_text="Glucose (mg/dL)", range=[40, 400], row=1, col=1)
        fig.update_yaxes(title_text="Glucose (mg/dL)", row=2, col=2)
        fig.update_xaxes(title_text="Hour of Day", row=2, col=2)

        return fig

    def save_figure(self, fig, filename='cgm_visualization.html'):
        """
        Save a Plotly figure to an HTML file.

        Args:
            fig: Plotly figure object
            filename: Output filename
        """
        if fig is None:
            print("No figure to save")
            return

        fig.write_html(filename)
        print(f"Visualization saved to: {filename}")

    def show_figure(self, fig):
        """
        Display a Plotly figure in the browser.

        Args:
            fig: Plotly figure object
        """
        if fig is None:
            print("No figure to show")
            return

        fig.show()


if __name__ == "__main__":
    # Example usage
    viz = CGMVisualizer()

    # Create and save various visualizations
    print("Creating glucose timeline...")
    timeline = viz.create_glucose_timeline(days=7)
    if timeline:
        viz.save_figure(timeline, 'glucose_timeline.html')

    print("\nCreating daily patterns...")
    daily = viz.create_daily_patterns(days=30)
    if daily:
        viz.save_figure(daily, 'daily_patterns.html')

    print("\nCreating hourly patterns...")
    hourly = viz.create_hourly_patterns()
    if hourly:
        viz.save_figure(hourly, 'hourly_patterns.html')

    print("\nCreating time in range chart...")
    tir = viz.create_time_in_range_chart(days=30)
    if tir:
        viz.save_figure(tir, 'time_in_range.html')

    print("\nCreating dashboard...")
    dashboard = viz.create_dashboard(days=7)
    if dashboard:
        viz.save_figure(dashboard, 'cgm_dashboard.html')
        print("\nDone! Open the HTML files in your browser to view the visualizations.")
