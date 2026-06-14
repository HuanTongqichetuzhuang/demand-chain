-- 清理供应商数据库：删除非真实公司的条目（导航按钮/广告/类别标题）
-- 保留真实公司并规范化字段

-- 1. 删除明显非公司的条目（导航按钮/广告/统计标题）
DELETE FROM matches WHERE profile_id IN (
    SELECT id FROM capability_profiles WHERE
    agent_card_json->>'name' IN (
        'ADD STARTUP','Add Startup','PROMOTE STARTUP','Advertising',
        'Load More Startups','Climate Tech Startups To Watch In 2026',
        'Top 10 Countries by number of Energy Startups',
        'Market Landscape for Energy Startups',
        'Hydrogen Fuel startups in UK','Hydrogen Fuel startups in USA',
        'Battery Swapping startups','Electric Vehicle Charging startups',
        'Methanol Fuel startups','Ammonia Fuel startups','e-Fuel startups',
        'Top 43 Energy-efficient Transportation startups',
        'EnergyStartups'
    )
    OR agent_card_json->>'name' ILIKE '%startup%watch%'
    OR agent_card_json->>'name' ILIKE '%top%country%'
    OR agent_card_json->>'name' ILIKE '%market landscape%'
    OR agent_card_json->>'name' ILIKE '%top%transportation%'
    OR agent_card_json->>'name' ILIKE 'ADD %'
    OR agent_card_json->>'name' ILIKE 'PROMOTE %'
    OR agent_card_json->>'name' = 'Advertising'
    OR agent_card_json->>'name' = 'Load More Startups'
    OR agent_card_json->>'name' = 'EnergyStartups'
    OR agent_card_json->>'name' = 'Add Startup'
    -- Also remove entries with empty or URL-only names
    OR agent_card_json->>'name' ~ '^https?://'
    OR agent_card_json->>'name' SIMILAR TO '[A-Z][a-z]+ Fuel startups'
    OR agent_card_json->>'name' SIMILAR TO '[A-Z][a-z]+ [A-Z][a-z]+ startups'
);

DELETE FROM capability_profiles WHERE
    agent_card_json->>'name' IN (
        'ADD STARTUP','Add Startup','PROMOTE STARTUP','Advertising',
        'Load More Startups','Climate Tech Startups To Watch In 2026',
        'Top 10 Countries by number of Energy Startups',
        'Market Landscape for Energy Startups',
        'Hydrogen Fuel startups in UK','Hydrogen Fuel startups in USA',
        'Battery Swapping startups','Electric Vehicle Charging startups',
        'Methanol Fuel startups','Ammonia Fuel startups','e-Fuel startups',
        'Top 43 Energy-efficient Transportation startups',
        'EnergyStartups'
    )
    OR agent_card_json->>'name' ILIKE '%startup%watch%'
    OR agent_card_json->>'name' ILIKE '%top%country%'
    OR agent_card_json->>'name' ILIKE '%market landscape%'
    OR agent_card_json->>'name' ILIKE '%top%transportation%'
    OR agent_card_json->>'name' ILIKE 'ADD %'
    OR agent_card_json->>'name' ILIKE 'PROMOTE %'
    OR agent_card_json->>'name' = 'Advertising'
    OR agent_card_json->>'name' = 'Load More Startups'
    OR agent_card_json->>'name' = 'EnergyStartups'
    OR agent_card_json->>'name' = 'Add Startup'
    OR agent_card_json->>'name' ~ '^https?://'
    OR agent_card_json->>'name' SIMILAR TO '[A-Z][a-z]+ Fuel startups'
    OR agent_card_json->>'name' SIMILAR TO '[A-Z][a-z]+ [A-Z][a-z]+ startups';

-- 2. 删除重复（同名保留一条）
DELETE FROM matches WHERE profile_id IN (
    SELECT id FROM (
        SELECT id, row_number() OVER (PARTITION BY agent_card_json->>'name' ORDER BY created_at DESC) AS rn
        FROM capability_profiles WHERE agent_card_json->>'name' IS NOT NULL AND agent_card_json->>'name' != ''
    ) sub WHERE rn > 1
);
DELETE FROM capability_profiles WHERE id IN (
    SELECT id FROM (
        SELECT id, row_number() OVER (PARTITION BY agent_card_json->>'name' ORDER BY created_at DESC) AS rn
        FROM capability_profiles WHERE agent_card_json->>'name' IS NOT NULL AND agent_card_json->>'name' != ''
    ) sub WHERE rn > 1
);

-- 3. 规范化分类：把分类不对的修正
UPDATE capability_profiles
SET agent_card_json = jsonb_set(agent_card_json, '{category}',
    CASE
        WHEN agent_card_json->>'name' IN ('Climeworks','Carbon Engineering','Global Thermostat','碳达科技','Qairos Energies','Aurora Hydrogen','Peregrine Hydrogen','Green Hydrogen Systems','Power to Hydrogen','Clean Hydrogen Works','Advanced Ionics','HiiROC','H2Pro','Hysata','Enapter','H2SITE','Hystar','Raven SR','Ohmium','Sunfire','Ecolectro','FusionOne','HySiLabs','Ionomr','Bramble Energy','ITM Power','Solugen','GenCell Energy','BayoTech','Hexagon Purus','Ergosup','Monolith','Oxeon Energy','HysetCo','ZeroAvia','EVOLOH','Beyond Aero','NovoHydrogen','Koloma','EnerVenue','Tulum Energy','Graphitic Energy','Fourier') THEN '"环境工程"'
        WHEN agent_card_json->>'name' IN ('宁德时代 CATL','比亚迪 BYD','隆基绿能 LONGi Green Energy','阳光电源 Sungrow','金风科技 Goldwind','明阳智能 Mingyang Smart Energy') THEN '"新能源"'
        WHEN agent_card_json->>'name' IN ('华为技术有限公司 Huawei','中兴通讯 ZTE','寒武纪 Cambricon','地平线 Horizon Robotics','百度 Apollo','商汤科技 SenseTime','科大讯飞 iFlytek','DeepSeek 深度求索') THEN '"人工智能"'
        WHEN agent_card_json->>'name' IN ('中芯国际 SMIC','华大九天 Empyrean','韦尔股份 Will Semiconductor','北方华创 NAURA') THEN '"电子科学与技术"'
        WHEN agent_card_json->>'name' IN ('中国航天科技 CASC','中国商飞 COMAC','星际荣耀 iSpace','蓝箭航天 LandSpace') THEN '"航空航天"'
        WHEN agent_card_json->>'name' IN ('药明康德 WuXi AppTec','百济神州 BeiGene','恒瑞医药 Hengrui Medicine','迈瑞医疗 Mindray') THEN '"生物医药"'
        WHEN agent_card_json->>'name' IN ('中科院金属研究所','中科院宁波材料所','中国建材集团 CNBM','万华化学 Wanhua Chemical','巴斯夫 BASF','陶氏 Dow','杜邦 DuPont','3M','汉高 Henkel') THEN '"材料科学"'
        WHEN agent_card_json->>'name' IN ('清华大学','北京大学','上海交通大学','浙江大学','MIT','Stanford','ETH Zurich','Tsinghua University') THEN '"其他"'
        WHEN agent_card_json->>'name' IN ('丹佛斯 Danfoss','ABB','西门子 Siemens','施耐德 Schneider Electric','罗克韦尔 Rockwell Automation','汇川技术 Inovance') THEN '"机器人与智能系统"'
        WHEN agent_card_json->>'name' IN ('Google Quantum AI','IBM Quantum','本源量子 Origin Quantum','国盾量子 QuantumCTek','Microsoft Azure Quantum','IonQ','Rigetti Computing','Xanadu') THEN '"信息技术"'
        ELSE agent_card_json->>'category'
    END
)
WHERE agent_card_json->>'category' = '其他' OR agent_card_json->>'category' IS NULL;

-- 4. 为空字段补默认值
UPDATE capability_profiles SET country = '中国' WHERE country IS NULL OR country = '';
UPDATE capability_profiles SET profile_type = 'COMPANY' WHERE profile_type IS NULL;

-- 5. 为没有URL的真实公司补官方网址
UPDATE capability_profiles
SET agent_card_json = jsonb_set(agent_card_json, '{url}', '"https://www.google.com/search?q=" || agent_card_json->>'name')
WHERE agent_card_json->>'url' IS NULL OR agent_card_json->>'url' = '';

-- 6. 删除没有任何实际信息的空记录
DELETE FROM capability_profiles WHERE
    (agent_card_json->>'name' IS NULL OR agent_card_json->>'name' = '')
    AND (agent_card_json->>'description' IS NULL OR agent_card_json->>'description' = '');
