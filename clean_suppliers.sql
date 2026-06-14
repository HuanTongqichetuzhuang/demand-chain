-- Delete obvious garbage supplier entries (listing headers, placeholders, UI text)
DELETE FROM capability_profiles
WHERE agent_card_json->>'name' IN (
  'Add Startup', 'ADD STARTUP', 'PROMOTE STARTUP',
  'Load More Startups', 'Methanol Fuel startups',
  'Battery Swapping startups', 'Top 7 Hydropower startups',
  'Top 77 Smart Grid startups',
  'Electric Vehicle Charging startups',
  'ENERGY STARTUPS BY COUNTRY',
  'Climate Tech Startups To Watch In 2026',
  'EnergyStartups', 'Advertising'
);
-- Show remaining count
SELECT count(*) as remaining FROM capability_profiles;
