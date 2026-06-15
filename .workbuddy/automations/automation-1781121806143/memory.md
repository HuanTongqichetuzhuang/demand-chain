# Auto-Crawler Automation Memory

Last execution: 2026-06-15

## Summary (Round 7)
- **Demands**: 10 collected, 10 inserted via /api/auto-demand (0 dup, 0 fail)
- **Suppliers**: 61 collected, 61 inserted via /api/auto-supplier (0 dup, 0 fail)
- **Total**: 71 new items (stable vs 71 last round)

### Sources results
| Source | Type | Items | Status |
|--------|------|-------|--------|
| USA.gov联邦挑战 | Demand | 7 | ✅ All inserted |
| XPRIZE竞赛 | Demand | 0 | ✅ No items found |
| NASA挑战 | Demand | 0 | ✅ No items found |
| MIT Solve | Demand | 0 | ✅ No items found |
| DARPA | Demand | - | ❌ DNS failure (getaddrinfo) |
| 新加坡航空航天挑战 | Demand | 0 | ✅ No items found |
| Climate-KIC | Demand | 0 | ✅ No items found |
| 国家自然科学基金委 | Demand | 0 | ✅ No items found |
| Grants.gov | Demand | 3 | ✅ All inserted (recovered from SSL issue) |
| HeroX挑战赛 | Demand | - | ❌ HTTP 404 Not Found |
| 中国各地企业技术需求 | Demand | 0 | ✅ No items found |
| 宁波创新挑战赛 | Demand | 0 | ✅ No items found |
| 苏州市揭榜挂帅 | Demand | 0 | ✅ No items found |
| 碳捕集初创企业 (StartUs) | Supplier | - | ❌ HTTP 403 Forbidden |
| 氢能初创企业 | Supplier | 60 | ✅ All inserted |
| 气候科技初创企业 | Supplier | 1 | ✅ Inserted |

### Notes
- Round 7 results consistent with Round 6: 71 total items, 0 duplicates
- Grants.gov recovered from previous SSL error, yielded 3 grants
- DARPA, HeroX, carbon capture sources still failing (no change)
- Backups saved to crawled_demands_20260615_060231.json / crawled_suppliers_20260615_060231.json

## Summary (Round 6)
- **Demands**: 10 collected, 10 inserted via /api/auto-demand (0 dup, 0 fail)
- **Suppliers**: 61 collected, 61 inserted via /api/auto-supplier (0 dup, 0 fail)
- **Total**: 71 new items (↓ from 107 last round)

### Sources results
| Source | Type | Items | Status |
|--------|------|-------|--------|
| USA.gov联邦挑战 | Demand | 7 | ✅ All inserted |
| XPRIZE竞赛 | Demand | 0 | ✅ No items found |
| NASA挑战 | Demand | 0 | ✅ No items found |
| MIT Solve | Demand | 0 | ✅ No items found |
| DARPA | Demand | - | ❌ DNS failure (getaddrinfo) |
| 新加坡航空航天挑战 | Demand | 0 | ✅ No items found |
| Climate-KIC | Demand | 0 | ✅ No items found |
| 国家自然科学基金委 | Demand | 0 | ✅ No items found |
| Grants.gov | Demand | 3 | ✅ All inserted |
| HeroX挑战赛 | Demand | - | ❌ HTTP 404 Not Found |
| 中国各地企业技术需求 | Demand | 0 | ✅ No items found |
| 宁波创新挑战赛 | Demand | 0 | ✅ No items found |
| 苏州市揭榜挂帅 | Demand | 0 | ✅ No items found |
| 碳捕集初创企业 (StartUs) | Supplier | - | ❌ HTTP 403 Forbidden |
| 氢能初创企业 | Supplier | 60 | ✅ All inserted |
| 气候科技初创企业 | Supplier | 1 | ✅ Inserted |

### Notes
- Demands dropped from 45→10: most sources returned 0 new items (source data may not have updated since last round)
- DARPA still DNS-failing, HeroX HTTP 404 (new source, not working yet)
- Carbon capture still HTTP 403
- Hydrogen source continues with UI noise ("Load More Startups", "Advertising", etc.)
- Zero duplicates across all 71 items
- Backups saved to crawled_demands_20260614_055856.json / crawled_suppliers_20260614_055856.json

## Summary (Round 4)
- **Demands**: 20 collected, 20 inserted via /api/auto-demand (0 dup, 0 fail)
- **Suppliers**: 62 collected, 62 inserted via /api/auto-supplier (0 dup, 0 fail)
- **Total**: 82 new items

### Sources results
| Source | Type | Items | Status |
|--------|------|-------|--------|
| USA.gov联邦挑战 | Demand | 11 | ✅ All inserted |
| XPRIZE竞赛 | Demand | 3 | ✅ All inserted |
| NASA挑战 | Demand | 0 | ✅ No items found |
| MIT Solve | Demand | 2 | ✅ All inserted |
| DARPA | Demand | - | ❌ DNS failure (getaddrinfo) |
| 新加坡航空航天挑战 | Demand | 1 | ✅ Inserted |
| Climate-KIC | Demand | 0 | ✅ No items found |
| 国家自然科学基金委 | Demand | 3 | ✅ All inserted |
| Grants.gov | Demand | - | ❌ SSL cert verify failed |
| 碳捕集初创企业 (StartUs) | Supplier | 1 | ✅ Inserted |
| 氢能初创企业 | Supplier | 60 | ✅ All inserted |
| 气候科技初创企业 (RankRed) | Supplier | 1 | ✅ Inserted |

### Quality notes
- Hydrogen source returned many non-company entries (category labels, UI text like "Load More Startups", "Advertising"), but API accepted them all as new
- No duplicates detected this round across all 82 items
- DARPA and Grants.gov continue to be blocked (network/SSL issues)
- JSON backup files saved

## Credentials
- crawler@demandchain.com / crawler2026!
- Session token: 041b41aa424b1f73c84ed9918cd52255

## Production Config
- SSH: root@8.154.26.92:2222
- Project path: /opt/demand-chain/
- Compose file: docker-compose.prod.yml
- MCP server: port 8000
- Web server: port 8080
- DB: pgvector/pgvector:pg16 on internal Docker network (db:5432)
- Image: demand-chain:slim (built locally, SCP to server)

## Known Issues
- DARPA page fetch fails with SSL EOF / DNS error
- Grants.gov SSL cert verification fails
- Hydrogen source quality: includes category labels and UI text as "companies"
- No dedup triggered this round (all 82 items treated as new)
