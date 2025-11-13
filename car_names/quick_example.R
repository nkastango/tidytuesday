# Quick Example - Test the car name categorization on a small sample
# Run this to see how the categorization works without downloading full EPA data

library(tidyverse)

# Load the reference database function
source("car_name_patterns.R")

# Create a sample of famous car models
sample_cars <- tibble(
  make = c(
    "Ford", "Ford", "Ford", "Ford", "Pontiac",
    "Chevrolet", "Chevrolet", "Chevrolet", "Chevrolet", "Chevrolet",
    "Dodge", "Dodge", "Dodge", "Plymouth",
    "GMC", "GMC", "Jeep", "Jeep", "Jeep",
    "Hyundai", "Hyundai", "Kia",
    "Audi", "BMW", "Mercedes-Benz",
    "Toyota", "Nissan", "Honda"
  ),
  model = c(
    "Mustang", "Bronco", "Explorer", "Thunderbird", "Firebird",
    "Impala", "Tahoe", "Suburban", "Blazer", "Malibu",
    "Charger", "Challenger", "Ram", "Barracuda",
    "Yukon", "Sierra", "Wrangler", "Cherokee", "Renegade",
    "Santa Fe", "Tucson", "Telluride",
    "A4", "M3", "C300",
    "Sequoia", "Pathfinder", "Pilot"
  ),
  year = 2020
) %>%
  mutate(
    model_clean = str_to_upper(model),
    model_first_word = word(model_clean, 1)
  )

# Build reference database
cat("Building reference databases...\n")
references <- create_reference_databases()

# Categorize
cat("Categorizing car names...\n")
categorized <- categorize_car_names(sample_cars, references)

# Display results
cat("\n=== Sample Car Name Categorization ===\n\n")
categorized %>%
  select(make, model, category, subcategory) %>%
  arrange(category, make, model) %>%
  print(n = Inf)

# Summary
cat("\n=== Category Summary ===\n")
categorized %>%
  count(category, sort = TRUE) %>%
  mutate(percentage = scales::percent(n / sum(n))) %>%
  print()

# Interesting patterns
cat("\n=== Interesting Patterns ===\n\n")

cat("🏔️  Geographic/Natural Features:\n")
categorized %>%
  filter(category == "Geographic/Place") %>%
  select(make, model, subcategory) %>%
  print()

cat("\n🐎 Animals:\n")
categorized %>%
  filter(category == "Animal") %>%
  select(make, model, subcategory) %>%
  print()

cat("\n🔥 Mythical Creatures:\n")
categorized %>%
  filter(category == "Mythical/Legendary") %>%
  select(make, model, subcategory) %>%
  print()

cat("\n🔢 Alphanumeric Model Codes:\n")
categorized %>%
  filter(category == "Alphanumeric/Model Code") %>%
  select(make, model) %>%
  print()

cat("\n✓ Example complete! Run car_name_patterns.R for the full analysis.\n")
