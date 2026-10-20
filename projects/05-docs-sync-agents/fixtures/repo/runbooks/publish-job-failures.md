---
service: scheduling-api
title: Schedule publish job failures
owner: platform-oncall
severity: sev2
last_reviewed: 2026-09-30
code_paths:
  - src/jobs/publish.js
---

## When to use
Publish jobs stay in `pending` for more than five minutes.

## Symptoms
Alert `publish_job_stuck` fires; customers report schedules not visible to agents.

## First 5 minutes
Check the job queue depth dashboard and the last deploy time.

## Mitigation
Retries back off at 100, 400 and 800 ms. If all three fail, requeue the job once.

## Verification
The job moves to `published` and the alert resolves.

## Rollback
Revert the last deploy if failures started with it.

## Escalation
Page the scheduling team lead after 30 minutes.

## Changelog
- 2026-09-30: backoff changed from 100/200/400 ms to 100/400/800 ms.
