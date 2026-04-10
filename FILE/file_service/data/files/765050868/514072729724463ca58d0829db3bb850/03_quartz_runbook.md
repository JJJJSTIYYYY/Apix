# Engineering Runbook: Quartz Cache

## Purpose
Quartz Cache stores precomputed answer fragments for a fictional analytics assistant.

## Maintenance Checklist
- Rotate cache snapshots every 7 days.
- Invalidate entries when schema version changes.
- Record the reason for each manual purge.

## Incident Signals
| Signal | Meaning | Action |
|---|---|---|
| hit_rate < 0.45 | Cache is stale | Trigger warm-up job |
| queue_depth > 1200 | Backpressure risk | Reduce batch size |
| checksum_mismatch | Snapshot corruption | Restore previous snapshot |

## Deployment Notes
1. Canary starts with 5% traffic.
2. Full rollout requires two green health checks.
3. Emergency disable flag: `QUARTZ_CACHE_BYPASS=true`

## FAQ
**Q:** What is the preferred restore source?  
**A:** The most recent verified snapshot in cold storage.

**Q:** Who approves a forced purge?  
**A:** The on-call reliability engineer.
