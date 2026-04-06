# Skill: CRM Data Processing

**Description:** Process customer data from CRM API responses — filter, aggregate, and report.

## What this skill does

- Parses raw CRM API JSON responses
- Filters customers by status (active / inactive / suspended)
- Aggregates revenue by plan tier (basic / pro / enterprise)
- Counts customers per segment
- Computes averages and identifies top-performing segments

## Input format

The input `raw_api_response` is a markdown-fenced JSON string:

```json
{
  "customers": [
    {
      "id": "cust_001",
      "name": "Alice Smith",
      "email": "alice@example.com",
      "status": "active",
      "plan": "pro",
      "monthly_revenue": 99.0,
      "signup_date": "2024-01-15"
    }
  ]
}
```

## Example tasks

- "Filter active customers and count them"
- "Sum monthly revenue for pro plan customers"
- "Find the plan with the highest total revenue"
- "List all customers who signed up after 2024-06-01"

## Notes

- `status` is always one of: `active`, `inactive`, `suspended`
- `plan` is always one of: `basic`, `pro`, `enterprise`
- `monthly_revenue` is a float in USD
- `signup_date` is always `YYYY-MM-DD`
