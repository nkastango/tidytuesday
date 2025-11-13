# Car Name Pattern Analysis

Analyzing the etymology and patterns in automobile model names - discovering what car manufacturers name their vehicles after!

## Overview

This project downloads comprehensive vehicle data from the EPA and categorizes car model names into patterns like:
- **Geographic features**: Denali (mountain), Yukon (territory), Tahoe (lake)
- **Animals**: Mustang, Impala, Cobra, Thunderbird
- **Mythical creatures**: Firebird, Phoenix, Dragon
- **Descriptive/Action words**: Explorer, Navigator, Blazer
- **Luxury/Prestige**: Regal, Imperial, Continental
- **Sport/Performance**: Turbo, Sprint, Challenger
- **Alphanumeric codes**: A4, M3, C300

## Usage

```r
# Run the full analysis
source("car_name_patterns.R")
```

This will:
1. Download EPA vehicle data (all cars sold in the US)
2. Categorize model names using reference databases
3. Generate analysis and statistics
4. Create visualizations
5. Save results to CSV

## Output Files

- `car_names_categories.png` - Distribution of naming categories
- `car_names_subcategories.png` - Top subcategories breakdown
- `car_names_evolution.png` - How naming trends changed over time
- `car_names_by_manufacturer.png` - Which brands prefer which patterns
- `car_names_categorized.csv` - Full dataset with categories

## Requirements

```r
install.packages(c("tidyverse", "jsonlite"))
```

## Extending the Analysis

Want to add more categories? Edit the `create_reference_databases()` function and add your own patterns!

Examples of patterns you could add:
- Weather phenomena (Tempest, Avalanche, Blizzard)
- Space/astronomy (Eclipse, Nova, Satellite)
- Gemstones (Diamante, Sapphire, Ruby)
- Historical figures or events
- Colors (Silverado, Blackwood)
- And more!
