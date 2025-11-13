# Car Name Pattern Analysis
# Analyzing the etymology and patterns in automobile model names

library(tidyverse)
library(stringr)
library(jsonlite)

# Function to download EPA vehicle data
get_car_data <- function() {
  # EPA provides comprehensive vehicle data
  url <- "https://www.fueleconomy.gov/feg/epadata/vehicles.csv.zip"

  temp <- tempfile()
  download.file(url, temp, mode = "wb")

  cars <- read_csv(unz(temp, "vehicles.csv"), show_col_types = FALSE)
  unlink(temp)

  # Extract unique model names
  cars %>%
    select(make, model, year) %>%
    distinct() %>%
    mutate(
      model_clean = str_to_upper(model),
      model_first_word = word(model_clean, 1)
    )
}

# Reference databases for pattern matching
create_reference_databases <- function() {

  # Geographic features (mountains, places, natural landmarks)
  geographic <- tibble(
    name = c(
      "DENALI", "YUKON", "TAHOE", "SIERRA", "SEQUOIA", "TUNDRA",
      "AVALANCHE", "SONATA", "TUCSON", "SANTA FE", "SEDONA",
      "SAVANA", "SUBURBAN", "OUTBACK", "FORESTER", "ALPINE",
      "ESCALADE", "ELDORADO", "MONACO", "ASPEN", "DURANGO",
      "MONTEGO", "MONTEREY", "MALIBU", "RIVIERA", "BONNEVILLE",
      "DAYTONA", "SEBRING", "TELLURIDE", "PALISADE", "TERRAIN",
      "ACADIA", "MOJAVE", "SAHARA", "RUBICON", "WRANGLER"
    ),
    category = "Geographic/Place",
    subcategory = c(
      rep("Mountain/Natural Feature", 6),
      rep("Natural Phenomenon", 1),
      rep("City/Place", 20),
      rep("Desert/Terrain", 4),
      rep("River/Natural Feature", 2),
      rep("Western/Frontier", 1)
    )
  )

  # Animals (real)
  animals_real <- tibble(
    name = c(
      "MUSTANG", "BRONCO", "PINTO", "COUGAR", "JAGUAR", "IMPALA",
      "BARRACUDA", "STINGRAY", "MANTA", "SPIDER", "VIPER", "COBRA",
      "HORNET", "BUG", "BEETLE", "CRICKET", "RABBIT", "FOX",
      "RAM", "CHARGER", "COLT", "MARLIN", "EAGLE", "HAWK",
      "FALCON", "RAVEN", "CONDOR", "THUNDERBIRD", "ROADRUNNER",
      "SKYLARK", "LYNX", "BOBCAT", "WILDCAT", "BISON", "STAG"
    ),
    category = "Animal",
    subcategory = c(
      rep("Mammal", 11),
      rep("Fish/Marine", 3),
      rep("Insect/Arachnid", 3),
      rep("Insect", 2),
      rep("Mammal", 2),
      rep("Livestock/Equine", 3),
      rep("Fish", 1),
      rep("Bird", 9),
      rep("Mammal", 4)
    )
  )

  # Mythical/Legendary
  mythical <- tibble(
    name = c(
      "FIREBIRD", "PHOENIX", "GRIFFIN", "DRAGON", "FURY",
      "DEMON", "TITAN", "ATLAS", "ODYSSEY", "VALKYRIE",
      "CENTAUR", "MINOTAUR", "CYCLONE", "THUNDERBOLT"
    ),
    category = "Mythical/Legendary",
    subcategory = c(
      rep("Mythical Creature", 5),
      rep("Demon/Monster", 1),
      rep("Titan/Giant", 2),
      rep("Epic/Legend", 2),
      rep("Norse", 1),
      rep("Mythical Creature", 2),
      rep("Natural Force", 2)
    )
  )

  # Descriptive/Action words
  descriptive <- tibble(
    name = c(
      "EXCURSION", "EXPEDITION", "EXPLORER", "NAVIGATOR", "PATHFINDER",
      "VOYAGER", "VENTURE", "JOURNEY", "QUEST", "BLAZER", "TRACKER",
      "TRAILBLAZER", "RANGER", "SCOUT", "COMMANDER", "PATRIOT",
      "FREEDOM", "LIBERTY", "VICTORY", "ACCLAIM", "ACHIEVA",
      "ASPIRE", "INSPIRE", "ELAN", "VERVE", "VIGOR", "SPIRIT",
      "SHADOW", "STEALTH", "PROWLER", "MARAUDER", "RAIDER",
      "REBEL", "ROGUE", "MAVERICK"
    ),
    category = "Descriptive/Action",
    subcategory = c(
      rep("Adventure/Exploration", 11),
      rep("Frontier/Western", 3),
      rep("Military/Authority", 2),
      rep("Patriotic", 3),
      rep("Aspirational", 7),
      rep("Energy/Movement", 3),
      rep("Stealth/Mystery", 3),
      rep("Aggressive", 3),
      rep("Rebellious", 3)
    )
  )

  # Luxury/Prestige
  luxury <- tibble(
    name = c(
      "REGAL", "ROYAL", "IMPERIAL", "CROWN", "CONTINENTAL",
      "DIPLOMAT", "AMBASSADOR", "MARQUIS", "LESABRE", "DEVILLE",
      "BROUGHAM", "PARK AVENUE", "FIFTH AVENUE", "NEW YORKER",
      "CELEBRITY", "PREMIERE", "PRESTIGE", "LEGEND", "PREMIER"
    ),
    category = "Luxury/Prestige",
    subcategory = c(
      rep("Royalty", 4),
      rep("Sophistication", 1),
      rep("Diplomatic", 2),
      rep("Nobility", 1),
      rep("French Luxury", 2),
      rep("Luxury Style", 1),
      rep("Prestigious Address", 3),
      rep("Status", 5)
    )
  )

  # Sport/Performance
  sport <- tibble(
    name = c(
      "RACE", "RACER", "TURBO", "GT", "GTI", "GTO", "SPRINT",
      "DART", "ARROW", "BULLET", "ROCKET", "JET", "LIGHTNING",
      "TEMPEST", "CYCLONE", "TORNADO", "CHALLENGER", "CHAMPION"
    ),
    category = "Sport/Performance",
    subcategory = c(
      rep("Racing", 2),
      rep("Performance Tech", 4),
      rep("Speed", 1),
      rep("Projectile/Fast", 9),
      rep("Weather/Power", 3),
      rep("Competition", 2)
    )
  )

  # Numbers/Alphanumeric (we'll detect these with regex)

  # Combine all references
  bind_rows(
    geographic,
    animals_real,
    mythical,
    descriptive,
    luxury,
    sport
  )
}

# Function to categorize car names
categorize_car_names <- function(cars_df, reference_df) {

  # Match against reference database
  cars_categorized <- cars_df %>%
    left_join(
      reference_df %>% select(name, category, subcategory),
      by = c("model_first_word" = "name")
    )

  # Add additional pattern-based categories
  cars_categorized <- cars_categorized %>%
    mutate(
      # Detect numbers
      has_numbers = str_detect(model_clean, "\\d"),

      # Detect single letter + numbers (like "A4", "M3", "C300")
      is_alphanumeric = str_detect(model_clean, "^[A-Z]{1,2}\\d"),

      # Update category for alphanumeric
      category = case_when(
        is_alphanumeric ~ "Alphanumeric/Model Code",
        !is.na(category) ~ category,
        TRUE ~ "Uncategorized"
      ),

      subcategory = case_when(
        is_alphanumeric ~ "Letter-Number Code",
        !is.na(subcategory) ~ subcategory,
        TRUE ~ "Unknown"
      )
    )

  cars_categorized
}

# Analysis and visualization functions
analyze_patterns <- function(categorized_cars) {

  # Summary by category
  category_summary <- categorized_cars %>%
    count(category, sort = TRUE) %>%
    mutate(percentage = n / sum(n) * 100)

  print("=== Car Name Categories ===")
  print(category_summary)

  # Top subcategories
  subcategory_summary <- categorized_cars %>%
    filter(category != "Uncategorized") %>%
    count(category, subcategory, sort = TRUE) %>%
    head(20)

  print("\n=== Top 20 Subcategories ===")
  print(subcategory_summary)

  # Evolution over time
  if ("year" %in% names(categorized_cars)) {
    time_evolution <- categorized_cars %>%
      filter(year >= 1990, category != "Uncategorized") %>%
      count(year, category) %>%
      group_by(year) %>%
      mutate(prop = n / sum(n))

    print("\n=== Category Trends Over Time ===")
    print(time_evolution %>% head(20))
  }

  # Examples by category
  print("\n=== Examples by Category ===")
  examples <- categorized_cars %>%
    filter(category != "Uncategorized") %>%
    group_by(category, subcategory) %>%
    slice_head(n = 3) %>%
    select(make, model, category, subcategory)

  print(examples)

  list(
    category_summary = category_summary,
    subcategory_summary = subcategory_summary,
    time_evolution = if(exists("time_evolution")) time_evolution else NULL,
    examples = examples
  )
}

# Create visualizations
create_visualizations <- function(categorized_cars, analysis_results) {

  # 1. Category distribution pie/bar chart
  p1 <- analysis_results$category_summary %>%
    filter(category != "Uncategorized") %>%
    ggplot(aes(x = reorder(category, n), y = n, fill = category)) +
    geom_col() +
    coord_flip() +
    labs(
      title = "Car Model Name Categories",
      subtitle = "Distribution of naming patterns across all vehicles",
      x = "Category",
      y = "Number of Models"
    ) +
    theme_minimal() +
    theme(legend.position = "none")

  ggsave("car_names_categories.png", p1, width = 10, height = 6, dpi = 300)

  # 2. Subcategory breakdown
  p2 <- analysis_results$subcategory_summary %>%
    head(15) %>%
    ggplot(aes(x = reorder(subcategory, n), y = n, fill = category)) +
    geom_col() +
    coord_flip() +
    labs(
      title = "Top 15 Car Name Subcategories",
      subtitle = "Specific patterns within broader categories",
      x = "Subcategory",
      y = "Number of Models"
    ) +
    theme_minimal() +
    theme(legend.position = "right")

  ggsave("car_names_subcategories.png", p2, width = 12, height = 7, dpi = 300)

  # 3. Time evolution (if data available)
  if (!is.null(analysis_results$time_evolution)) {
    p3 <- analysis_results$time_evolution %>%
      ggplot(aes(x = year, y = prop, color = category, group = category)) +
      geom_line(linewidth = 1) +
      geom_point() +
      scale_y_continuous(labels = scales::percent) +
      labs(
        title = "Evolution of Car Naming Patterns Over Time",
        subtitle = "Proportion of different naming categories (1990-present)",
        x = "Year",
        y = "Proportion",
        color = "Category"
      ) +
      theme_minimal() +
      theme(legend.position = "bottom")

    ggsave("car_names_evolution.png", p3, width = 12, height = 7, dpi = 300)
  }

  # 4. Manufacturer preferences
  p4 <- categorized_cars %>%
    filter(category != "Uncategorized") %>%
    count(make, category) %>%
    group_by(make) %>%
    filter(n() >= 5) %>%  # Only makers with 5+ categorized models
    ggplot(aes(x = category, y = make, fill = n)) +
    geom_tile() +
    scale_fill_viridis_c() +
    labs(
      title = "Manufacturer Naming Preferences",
      subtitle = "Which car makers prefer which naming patterns?",
      x = "Category",
      y = "Manufacturer",
      fill = "Count"
    ) +
    theme_minimal() +
    theme(axis.text.x = element_text(angle = 45, hjust = 1))

  ggsave("car_names_by_manufacturer.png", p4, width = 12, height = 10, dpi = 300)

  print("\n✓ Visualizations saved!")
}

# Main execution
main <- function() {
  cat("🚗 Car Name Pattern Analysis\n")
  cat("=" + rep("=", 50), "\n\n")

  cat("📥 Downloading EPA vehicle data...\n")
  cars <- get_car_data()
  cat(sprintf("✓ Loaded %d unique car models\n\n", nrow(cars)))

  cat("📚 Building reference databases...\n")
  references <- create_reference_databases()
  cat(sprintf("✓ Created reference database with %d entries\n\n", nrow(references)))

  cat("🔍 Categorizing car names...\n")
  categorized <- categorize_car_names(cars, references)
  cat("✓ Categorization complete\n\n")

  cat("📊 Analyzing patterns...\n")
  analysis <- analyze_patterns(categorized)

  cat("\n📈 Creating visualizations...\n")
  create_visualizations(categorized, analysis)

  # Save the categorized dataset
  write_csv(categorized, "car_names_categorized.csv")
  cat("\n💾 Full dataset saved to 'car_names_categorized.csv'\n")

  cat("\n✅ Analysis complete!\n")

  invisible(list(cars = categorized, analysis = analysis))
}

# Run the analysis
if (sys.nframe() == 0) {
  results <- main()
}
