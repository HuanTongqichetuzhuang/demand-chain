# NGI Zero Commons Fund — Project Proposal

## 1. Project Information

| Field | Value |
|---|---|
| **Project name** | Demand Chain Platform |
| **One-line description** | An open, AI-powered innovation infrastructure that connects problem-holders with problem-solvers using Agent-to-Agent (A2A) protocol |
| **License** | Apache 2.0 |
| **Repository** | https://github.com/HuanTongqichetuzhuang/demand-chain |
| **Website** | https://demand-chain.duckdns.org |
| **Existing funding** | None (community-funded) |
| **Target budget** | €45,000 |

## 2. Problem Statement

There is a fundamental information asymmetry in innovation: **problem-holders don't know who can solve their problems, and problem-solvers don't know what problems need solving.**

- A factory needs a 1200°C heat-resistant sensor for pipeline monitoring → they Google, call vendors, attend trade shows — weeks lost.
- A university lab develops a new self-healing polymer → they publish a paper, and wait years for industry to notice.
- A government agency needs a carbon capture solution → they issue an RFP, and only large incumbents respond.

This is not a technology gap — it is a **matching gap**. The information exists, but it is fragmented across languages, disciplines, geographies, and organization types.

Existing solutions (procurement platforms, trade fairs, consulting) all share a common flaw: they require manual human effort at every step. They do not scale.

## 3. Solution

The **Demand Chain Platform** uses AI agents as intermediaries:

1. A human describes a need in **natural language** — "I need a biodegradable plastic that decomposes in seawater within 6 months"
2. Their **personal AI Agent** structures this into a formal demand record (category, IPC class, TRL level, constraints) and publishes it
3. The platform's **matching engine** — based on Google's A2A (Agent-to-Agent) protocol — finds the best-matching supplier capabilities
4. The supplier's AI Agent receives a notification and presents the opportunity to its human

**Key innovation:** The human only makes two decisions — "I need this" and "I want to work with them." All the searching, filtering, and matching is done by AI agents communicating in real-time.

## 4. Current Status

The platform is **fully functional today**:

- **66 real demands** across 31 industry categories (energy, materials, aerospace, biotech, etc.)
- **20 real supplier profiles** (companies and research labs globally)
- **Functional web interface**: registration, profile management, forum with voting/replies, demand square with detail modals
- **MCP server with 56+ tools**: agents can publish demands, search capabilities, manage matches
- **Working multilingual support** (Chinese/English toggle)
- **GitHub Sponsors/Afdian donation channels** active

## 5. What We Will Build with NGI Zero Funding

**Phase 1 — Core Matching Engine (€15,000)**

- Implement vector embedding of demands and capabilities (using open-source models)
- Build a multi-dimensional matching scorer (text similarity × IPC code overlap × TRL alignment × country constraints)
- API endpoints for ranked match results
- Automated match notification emails

**Phase 2 — Agent Communication Infrastructure (€15,000)**

- Full A2A protocol implementation for agent-to-agent negotiation
- Session management for multi-round conversations between human delegates
- Privacy-preserving capability disclosure (agents can ask clarifying questions without exposing human identity)
- Integration tests with Claude, GPT, DeepSeek agents

**Phase 3 — Community & Internationalization (€10,000)**

- Complete English localization of the entire UI
- Open Graph + i18n for SEO (search engines index in both languages)
- Onboarding flow improvements and tutorial updates
- Forum seeding with 5 industry discussion topics (admin posts to kickstart conversations)

**Phase 4 — Operations & Outreach (€5,000)**

- Server hosting for 12 months (2 vCPU, 4GB RAM)
- Domain name and HTTPS certificate
- SEO submission to Google/Bing
- Documentation improvements and API reference

## 6. Deliverables

| Deliverable | Month |
|---|---|
| Matching engine v1 with vector embeddings | M2 |
| REST API for ranked matching | M3 |
| A2A agent communication (basic negotiation) | M4 |
| Privacy-preserving agent handshake | M5 |
| Full English localization | M6 |
| SEO, tutorial update, community seeding | M6 |
| Public launch + NLnet report | M6 |

## 7. Budget Breakdown

| Item | Cost (EUR) |
|---|---|
| Developer time (1 FTE × 6 months, part-time) | €30,000 |
| Server infrastructure (12 months, Hetzner) | €3,000 |
| Domain + email hosting | €500 |
| Open-source model inference (GPU spot instances) | €4,000 |
| Security audit (external) | €5,000 |
| Legal review (privacy compliance) | €2,500 |
| **Total** | **€45,000** |

## 8. Team

| Role | Name | Background |
|---|---|---|
| Founder & Lead Developer | HuanTongqichetuzhuang | Full-stack developer, open-source advocate. Built the entire platform solo over 4 months. |
| Advisor | TBD | Seeking a European open-source advisor for NGI compliance |

We are open to adding team members recommended by NLnet.

## 9. Sustainability

After the NGI grant period, the platform will sustain itself through:

1. **GitHub Sponsors / Afdian** — already set up, ongoing community donations
2. **Open Collective** — for transparent enterprise sponsorship
3. **Matched contribution** — enterprises using the platform for internal innovation can self-host or contribute
4. **Future grants** — Sovereign Tech Fund (Germany), Linux Foundation, Prototype Fund

The core software will remain **Apache 2.0 — forever free and open-source**.

## 10. Alignment with NGI Zero Goals

- ✓ **Open Internet infrastructure** — A2A protocol is an open standard, not a proprietary platform
- ✓ **Privacy by design** — Agents communicate without exposing human identity until a match is found
- ✓ **Decentralization** — Anyone can self-host their own instance; no vendor lock-in
- ✓ **European values** — GDPR-compliant by design (no personal data stored without consent)
- ✓ **Open source** — Apache 2.0, public on GitHub since day one

---

*Submitted by HuanTongqichetuzhuang — June 2026*

