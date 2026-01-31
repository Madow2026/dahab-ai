# Implementation Plan for Dahab AI Enhancements

## Status: Multi-Phase Project

This document outlines the comprehensive enhancement plan based on the requirements provided.

---

## ✅ PHASE 0: COMPLETED
- [x] Add 28 economic RSS news sources (up from 3)
- [x] Professional institutional-grade market commentary
- [x] Improved News page UI with professional styling
- [x] System diagnostic script created

---

## 🔧 PHASE 1: CRITICAL STABILITY FIXES (Priority 1)
**Estimated Time: 4-6 hours**

### 1.1 Worker Hardening
- [ ] Wrap worker cycle in bulletproof try/except
- [ ] Enhanced heartbeat discipline (start/end/error)
- [ ] Worker state tracking (RUNNING/DELAYED/ERROR/STOPPED)
- [ ] Prevent silent worker death

### 1.2 Market Delta Fix
- [ ] Query last 2 price snapshots per asset
- [ ] Calculate real deltas (abs and %)
- [ ] Handle edge cases (only 1 snapshot, no data)
- [ ] Fix sentiment score calculation (0-100 scale)

### 1.3 Validation
- [ ] Run system_diagnostic.py before changes
- [ ] Run py_compile on all files
- [ ] Test worker.py --once
- [ ] Verify deltas show correctly

**Risk Level:** LOW (mostly additive changes)

---

## 🚀 PHASE 2: WORKER WATCHDOG & AUTO-RESTART (Priority 2)
**Estimated Time: 3-4 hours**

### 2.1 Watchdog Script
- [ ] Create start_worker_watchdog.py
- [ ] Subprocess management with restart logic
- [ ] Log restart attempts to DB
- [ ] Windows-compatible implementation

### 2.2 Unified Startup
- [ ] Create/update start_all.ps1
- [ ] Launch Streamlit + Watchdog Worker
- [ ] Handle graceful shutdown
- [ ] Test on Windows

**Risk Level:** MEDIUM (background process management)

---

## 📊 PHASE 3: UI ENHANCEMENTS (Priority 3)
**Estimated Time: 6-8 hours**

### 3.1 Sidebar Badge Counters
- [ ] Create page_visits table (migration)
- [ ] Track last_seen_id per page
- [ ] Compute new counts dynamically
- [ ] Reset badge on page visit
- [ ] Test with session persistence

### 3.2 Forecast Visualization
- [ ] Add timestamp to forecast listings
- [ ] Create visual forecast cards
- [ ] Mini line charts (Plotly)
- [ ] Professional card styling
- [ ] 5-card grid layout

### 3.3 News UI Polish
- [ ] Professional card design
- [ ] Sentiment/category badges
- [ ] Affected assets chips
- [ ] Consistent spacing

**Risk Level:** LOW-MEDIUM (UI only, no logic changes)

---

## 🎯 PHASE 4: ACCURACY & EVALUATION (Priority 4)
**Estimated Time: 4-5 hours**

### 4.1 Forecast Evaluation Logic
- [ ] Evaluate forecasts where due_at <= now
- [ ] Find actual price at/after due_at
- [ ] Fill evaluation_result, evaluated_at
- [ ] Calculate error metrics

### 4.2 Accuracy Page Updates
- [ ] Show evaluated forecasts section
- [ ] Accuracy by asset/horizon
- [ ] Confusion matrix counts
- [ ] Pending forecasts by horizon

### 4.3 PowerShell Safety
- [ ] Create scripts/db_checks.py
- [ ] Safe SQL query snippets
- [ ] Avoid < interpretation issues

**Risk Level:** MEDIUM (database writes, logic changes)

---

## 💼 PHASE 5: PAPER PORTFOLIO ENHANCEMENTS (Priority 5)
**Estimated Time: 6-8 hours**

### 5.1 Risk Profile System
- [ ] Add portfolio_profiles table
- [ ] User risk selection UI (Conservative/Balanced/Aggressive)
- [ ] Capital slider (100-100,000)
- [ ] Max drawdown limits per profile

### 5.2 Enhanced Auto-Trading
- [ ] Position sizing by risk profile
- [ ] Max exposure per asset
- [ ] Volatility checks
- [ ] Trade logging with reasons
- [ ] "Explain this trade" expander

### 5.3 Compliance
- [ ] Strong educational disclaimer
- [ ] Remove background_gradient or add matplotlib
- [ ] Test all features

**Risk Level:** MEDIUM-HIGH (trading logic changes)

---

## 🌍 PHASE 6: ARABIC TRANSLATION (Priority 6)
**Estimated Time: 3-4 hours**

### 6.1 Language Toggle
- [ ] Add EN/AR switch in UI
- [ ] Store preference in session_state
- [ ] Persist to DB (optional)

### 6.2 Commentary Translation
- [ ] Generate professional Arabic commentary
- [ ] Keep tickers in English
- [ ] MENA business Arabic style
- [ ] Toggle between EN/AR views

**Risk Level:** LOW (additive feature)

---

## ✅ PHASE 7: VALIDATION & DOCUMENTATION
**Estimated Time: 2-3 hours**

### 7.1 Full System Test
- [ ] py_compile all files
- [ ] worker.py --once (no errors)
- [ ] DB counts verification
- [ ] All pages load without crash

### 7.2 Documentation
- [ ] List of files changed
- [ ] Key code snippets
- [ ] Windows startup commands
- [ ] Troubleshooting guide

---

## 📋 TOTAL ESTIMATED TIME: 28-38 hours
**Recommended Schedule:** 1-2 weeks with proper testing

---

## 🎯 RECOMMENDED APPROACH

### Option A: Incremental (SAFEST)
- Implement one phase per day
- Test thoroughly between phases
- Roll back if issues arise
- Total: 6-7 days

### Option B: Weekend Sprint (RISKY)
- Focus on Phases 1-3 only
- 8-10 hour coding sessions
- May miss edge cases
- Total: 2-3 days

### Option C: Professional (RECOMMENDED)
- Phase 1 (critical fixes): Day 1
- Phase 2 (watchdog): Day 2
- Phase 3 (UI): Days 3-4
- Phase 4 (accuracy): Day 5
- Phase 5-6 (enhancements): Days 6-7
- Phase 7 (validation): Day 8
- **Total: 8 days with proper testing**

---

## 🚨 RISKS & MITIGATION

### High-Risk Areas:
1. **Worker watchdog** - could break existing worker
   - Mitigation: Test separately, keep old start method
   
2. **Evaluation logic** - could corrupt forecast data
   - Mitigation: Backup DB before changes, test on copy
   
3. **Auto-trading changes** - could execute bad trades
   - Mitigation: Paper-only, extensive logging, kill switch

### Zero-Risk Areas:
1. UI styling changes
2. Adding new RSS feeds
3. Diagnostic scripts
4. Documentation

---

## 📞 NEXT STEPS

**To proceed, choose one of:**

1. **Start Phase 1 now** (critical fixes, 4-6 hours)
2. **Run diagnostic only** (verify current issues)
3. **Pick specific features** (focus on what matters most)
4. **Hire additional help** (parallel development)

**Current recommendation:** Start with Phase 1 (critical stability) since it has highest ROI and lowest risk.
