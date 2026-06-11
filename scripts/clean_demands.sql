-- Clean junk demands from demand_chain (phase 2): URLs, nav text, NSFC, USA.gov, dupes, tests, nonsense
DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ~ '^https?://' OR raw_text ~ '^www\.');
DELETE FROM demands WHERE raw_text ~ '^https?://' OR raw_text ~ '^www\.';

DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ILIKE '%NSFC%');
DELETE FROM demands WHERE raw_text ILIKE '%NSFC%';

DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ILIKE '%USAGov%' OR raw_text ILIKE '%1-844%' OR raw_text ILIKE '%call us at%');
DELETE FROM demands WHERE raw_text ILIKE '%USAGov%' OR raw_text ILIKE '%1-844%' OR raw_text ILIKE '%call us at%';

DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ILIKE '%partner with%' OR raw_text ILIKE '%report a website%' OR raw_text ILIKE '%report website%' OR raw_text ILIKE '%accessibility%');
DELETE FROM demands WHERE raw_text ILIKE '%partner with%' OR raw_text ILIKE '%report a website%' OR raw_text ILIKE '%report website%' OR raw_text ILIKE '%accessibility%';

DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ILIKE '%terms of service%' OR raw_text ILIKE '%terms % conditions%');
DELETE FROM demands WHERE raw_text ILIKE '%terms of service%' OR raw_text ILIKE '%terms % conditions%';

DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ILIKE '%get.agorize%' OR raw_text ILIKE '%powered by agorize%' OR raw_text ILIKE '%create an account%');
DELETE FROM demands WHERE raw_text ILIKE '%get.agorize%' OR raw_text ILIKE '%powered by agorize%' OR raw_text ILIKE '%create an account%';

DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ILIKE '%branches of government%' OR raw_text ILIKE '%feature article%' OR raw_text ILIKE '%website usage%');
DELETE FROM demands WHERE raw_text ILIKE '%branches of government%' OR raw_text ILIKE '%feature article%' OR raw_text ILIKE '%website usage%';

DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ILIKE '%become a solver%' OR raw_text ILIKE '%become a reviewer%' OR raw_text ILIKE '%meet the solver%');
DELETE FROM demands WHERE raw_text ILIKE '%become a solver%' OR raw_text ILIKE '%become a reviewer%' OR raw_text ILIKE '%meet the solver%';

DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ILIKE '%grand challenge%' OR raw_text ILIKE '%centennial challenge%' OR raw_text ILIKE '%outreach%');
DELETE FROM demands WHERE raw_text ILIKE '%grand challenge%' OR raw_text ILIKE '%centennial challenge%' OR raw_text ILIKE '%outreach%';

DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ILIKE '%federal agency%' OR raw_text ILIKE '%state government%' OR raw_text ILIKE '%local government%' OR raw_text ILIKE '%elected official%');
DELETE FROM demands WHERE raw_text ILIKE '%federal agency%' OR raw_text ILIKE '%state government%' OR raw_text ILIKE '%local government%' OR raw_text ILIKE '%elected official%';

DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ILIKE '%site map%' OR raw_text ILIKE '%faq%' OR raw_text ILIKE '%disclaimer%' OR raw_text ILIKE '%foia%');
DELETE FROM demands WHERE raw_text ILIKE '%site map%' OR raw_text ILIKE '%faq%' OR raw_text ILIKE '%disclaimer%' OR raw_text ILIKE '%foia%';

DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ILIKE '%appendix%' OR raw_text ILIKE '%constitution%' OR raw_text ILIKE '%regulations%' OR raw_text ILIKE '%annual report%');
DELETE FROM demands WHERE raw_text ILIKE '%appendix%' OR raw_text ILIKE '%constitution%' OR raw_text ILIKE '%regulations%' OR raw_text ILIKE '%annual report%';

DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ILIKE '%leadership%' OR raw_text ILIKE '%at a glance%' OR raw_text ILIKE '%guide to program%' OR raw_text ILIKE '%application and review%');
DELETE FROM demands WHERE raw_text ILIKE '%leadership%' OR raw_text ILIKE '%at a glance%' OR raw_text ILIKE '%guide to program%' OR raw_text ILIKE '%application and review%';

DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ILIKE '%synthesis evidence%' OR raw_text ILIKE '%international evaluation%' OR raw_text ILIKE '%directory of%' OR raw_text ILIKE '%all topics%');
DELETE FROM demands WHERE raw_text ILIKE '%synthesis evidence%' OR raw_text ILIKE '%international evaluation%' OR raw_text ILIKE '%directory of%' OR raw_text ILIKE '%all topics%';

DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ILIKE '%about this site%' OR raw_text ILIKE '%agree to support%' OR raw_text ILIKE '%using this site%' OR raw_text ILIKE '%about the u.s.%');
DELETE FROM demands WHERE raw_text ILIKE '%about this site%' OR raw_text ILIKE '%agree to support%' OR raw_text ILIKE '%using this site%' OR raw_text ILIKE '%about the u.s.%';

DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ILIKE '%government agencies%' OR raw_text ILIKE '%department of%' OR raw_text ILIKE '%executive%' OR raw_text ILIKE '%legislative%' OR raw_text ILIKE '%judicial%');
DELETE FROM demands WHERE raw_text ILIKE '%government agencies%' OR raw_text ILIKE '%department of%' OR raw_text ILIKE '%executive%' OR raw_text ILIKE '%legislative%' OR raw_text ILIKE '%judicial%';

DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ILIKE '%the white house%' OR raw_text ILIKE '%u.s. house%' OR raw_text ILIKE '%u.s. senate%' OR raw_text ILIKE '%governor%');
DELETE FROM demands WHERE raw_text ILIKE '%the white house%' OR raw_text ILIKE '%u.s. house%' OR raw_text ILIKE '%u.s. senate%' OR raw_text ILIKE '%governor%';

DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ILIKE '%icfcrt%' OR raw_text ILIKE '%off the hook%' OR raw_text ILIKE '%hook up%' OR raw_text ILIKE '%get hooked%' OR raw_text ILIKE '%privacy policy%');
DELETE FROM demands WHERE raw_text ILIKE '%icfcrt%' OR raw_text ILIKE '%off the hook%' OR raw_text ILIKE '%hook up%' OR raw_text ILIKE '%get hooked%' OR raw_text ILIKE '%privacy policy%';

-- Remove duplicates (keep first occurrence)
DELETE FROM matches WHERE demand_id IN (SELECT id FROM (SELECT id, row_number() OVER (PARTITION BY raw_text ORDER BY created_at) AS rn FROM demands WHERE raw_text IS NOT NULL) s WHERE s.rn > 1);
DELETE FROM demands WHERE id IN (SELECT id FROM (SELECT id, row_number() OVER (PARTITION BY raw_text ORDER BY created_at) AS rn FROM demands WHERE raw_text IS NOT NULL) s WHERE s.rn > 1);

-- Remove test / very short
DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ILIKE '%test%crawler%');
DELETE FROM demands WHERE raw_text ILIKE '%test%crawler%';

DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE char_length(raw_text) < 30);
DELETE FROM demands WHERE char_length(raw_text) < 30;

-- Remove repetitive Solve/XPRIZE stub entries that are just challenge category names
DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text IN ('Innovative Financing','Youth Innovation','Indigenous Communities','Economic Prosperity','Solve Challenge Finals','Challenges and prize competitions','Solve Challenge Finals'));
DELETE FROM demands WHERE raw_text IN ('Innovative Financing','Youth Innovation','Indigenous Communities','Economic Prosperity','Solve Challenge Finals','Challenges and prize competitions','Solve Challenge Finals');

-- Remove pseudo-science
DELETE FROM matches WHERE demand_id IN (SELECT id FROM demands WHERE raw_text ~ '减质量.*减到零|一直减少.*零');
DELETE FROM demands WHERE raw_text ~ '减质量.*减到零|一直减少.*零';
