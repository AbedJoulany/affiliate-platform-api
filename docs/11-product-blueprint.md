# Product Blueprint

**Current product:** AI Affiliate Marketing Automation Platform

## Scope

The product serves an affiliate/content marketer who wants to discover promising products, evaluate them, create marketing content with AI, review it, schedule it, publish it, and measure marketing activity.

### Core loop

**DISCOVER → EVALUATE → SELECT → CREATE WITH AI → REVIEW → QUEUE → SCHEDULE → PUBLISH → MEASURE**

## Product A: included

- Product discovery
- AliExpress product import
- Product catalog and product intelligence
- Product affiliate URL/opportunity data
- AI marketing content generation
- Content variants and review workflow
- Publishing queue
- Scheduling and publishing
- Telegram channel integration
- Operational dashboard and analytics foundation
- Authentication and workspace foundations where already implemented

## Product B: removed

The following affiliate-network concepts are intentionally outside the product scope and have been removed from the application code:

- Affiliate network profiles
- Advertiser entities
- Campaign management
- Affiliate ↔ Campaign enrollment
- Network tracking links
- Conversion settlement records
- Commission calculation/settlement
- Payout management

`Product.commission_rate` and `Product.affiliate_url` remain valid product/opportunity fields. They do not represent a commission ledger or affiliate-network settlement system.

## Domain model

### User

A platform account with an operator `ADMIN` role or normal `USER` role.

### Product

The primary business work unit. It contains product information, marketplace data, opportunity/affiliate URL information, and scoring data used during discovery and evaluation.

### AI Content

Marketing copy generated from product context. Generation is a content-production capability, not a general autonomous agent.

### QueueItem

A marketing publication unit containing content, destination, schedule, and publication status.

### TelegramChannel

A publishing destination/adapter. Telegram is a channel, not the business domain itself.

### Analytics

Marketing and operational measurement. It must not be presented as affiliate-network settlement analytics.

## Design boundary

Do not reintroduce campaigns, affiliate profiles, advertisers, conversions, commission settlement, or payout workflows unless the product strategy explicitly changes back to an affiliate-network platform.
