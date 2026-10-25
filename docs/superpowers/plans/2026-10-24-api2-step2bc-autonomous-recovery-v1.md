# API 2 Step 2B + Step 2C Permanent Execution Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Permanently enforce API2-only autonomous failure recovery through independently proven GREEN + FROZEN.

**Architecture:** Use self-contained `api2_*` authority modules rooted at `api2-main`; proof and frozen state use separate API2-owned refs. Every post-failure mutation requires new Anti-Loop evidence, Step 2C root cause, passing Step 2B, and single-use Step 2A authorization.

**Tech Stack:** Python 3.13, pytest, canonical JSON/SHA-256, GitHub refs.

**Spec:** `docs/superpowers/specs/2026-10-24-api2-step2bc-autonomous-recovery-v1-design.md`

## Global Constraints
- No foreign-system authority input or evidence.
- One active API2 problem/path.
- No blind retry.
- Normal technical failures recover autonomously.
- GREEN requires complete acceptance proof.
- FROZEN requires API2 registry readback.
- No product/model mutation.

## Tasks
1. TDD API2 isolation + Anti-Loop.
2. TDD Step 2C autonomous investigation/human-only classification.
3. TDD Step 2B reliability gate.
4. TDD Step 2A single-use authority + ordered controller/live status.
5. TDD API2-native execution-plan compiler and monotonic checkpoint history.
6. TDD API2 freeze registry and whole-stack certification.
7. Seal exact candidate, API2 proof-registry readback, merge to `api2-main`, merged-content verification, API2 freeze-registry write/readback.
