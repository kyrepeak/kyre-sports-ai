## DevSystem change contract

**Scope**
- [ ] This PR changes the smallest necessary surface.
- [ ] I am not silently modifying a frozen model/runtime contract.
- [ ] Any new sport/domain has a dedicated critical test lane before activation.

**Verification**
- [ ] DevSystem classifier identified the intended domain(s).
- [ ] Permanent contract is green.
- [ ] Regression shield is green.
- [ ] Affected sport critical tests are green.
- [ ] Browser QA is green when UI/shared routing is affected.

**Production**
- [ ] No deployment is required, or the deployment path is explicitly identified.
- [ ] Production verification will run after merge when relevant.
- [ ] Rollback target is known.

**Safety**
- [ ] Missing data fails visibly rather than being fabricated.
- [ ] Official identity rules are preserved.
- [ ] Sportsbook/market influence has not changed unless this PR explicitly versions that model contract.
