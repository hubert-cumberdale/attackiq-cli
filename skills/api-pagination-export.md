# Skill: API Pagination + Export Patterns

## Purpose
Implement paginated API fetches and export flows (CSV/JSON) using existing helpers.

## Constraints
- Use `paginate_results` or the pagination snippet for list endpoints.
- Set explicit timeouts and honor TLS verification flags.
- Keep memory usage bounded; stream or chunk when possible.

## Standard Steps
1. Confirm endpoint supports `page`/`page_size` and `next` in responses.
2. Build or reuse pagination loop; cap pages if required.
3. Transform items into export rows (dicts) with stable ordering.
4. Write output via existing export helpers or minimal file I/O.
5. Add tests for pagination boundaries and empty results.

## Example Commands
- `attackiq export scenarios --page-size 200 --format csv`
- `attackiq export assessments --page-size 200 --format json`

## Test Expectations
- Unit tests for pagination loops and export formatting.
- Run `pytest -k export` when touching export logic.
