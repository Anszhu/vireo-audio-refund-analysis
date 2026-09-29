# 3-minute screen recording script (no slides)

*Speak naturally; ≈ 400 words total. Have the Streamlit app open on page 1.*

**0:00-0:20 - Problem and what was built**
"Finance said refunds were over a crore a quarter; the helpdesk said about eleven lakh. I built a small pipeline and Streamlit tool that reconciles the two, breaks refunds down by month, reason code and agent, and flags refund-plus-replacement exceptions. The answer is ₹67.10 lakh total, about ₹11.18 lakh a quarter."

**0:20-0:50 - Prompt(s) used**
"I used Claude with one long brief: act as data engineer and analyst, read every file first, don't fabricate numbers, don't silently fix data, audit before building, then reconcile, validate, build the tool. Key instructions: normalise money only with evidence, use agent_id, don't accuse individual agents, and label assumptions. For the final pass I asked Codex to audit validation claims, handoffs, privacy, and consistency without changing the analysis. No paid API is used and the tool makes no AI calls."

**0:50-1:35 - Tool walkthrough**
"Page 6, the Board Pack: the refund position, the main drivers, the control issue and the opportunity on one screen. Page 5, the reconciliation: raw ₹23.01 crore, minus re-imported duplicates, minus the legacy paise scaling, equals ₹67.10 lakh. Legacy amounts are exactly a hundred times the helpdesk amounts on every duplicate pair. Page 3 compares agents only within their own team - nobody is outside the normal range. Page 4 lists the exception cases with the evidence and where the evidence comes from."

**1:35-2:00 - What changed between versions**
"The first exception rule called same-order cross-ticket cases 'likely'. That was too aggressive, so I downgraded them to 'ambiguous'. I also fixed text rules after reading a 60-ticket sample, then checked on a fresh 40-ticket hold-out."

**2:00-2:25 - What was discarded**
"I dropped an LLM classifier - rules do the job on this templated text, cost nothing and reproduce exactly. I also didn't re-code GW-OTHER: it is shown as 'requires review', because the dropdown stays the source of record."

**2:25-2:50 - Business result**
"Refund-plus-replacement tickets are 7.4% of refund tickets. Taking that to 1 percent is a planning assumption, not a forecast, and would be worth about ₹55,925 a quarter; the sensitivity table shows other rates. One run costs zero rupees in model cost."

**2:50-3:00 - Validation and limitation**
"The project records 26 automated checks passing: 21 structural and 5 independent recomputations. The 100-ticket samples and 40-case secondary review were AI-labelled, not independently human-reviewed. Claude also contributed to the rules, so the 37 out of 40 exact agreement may be optimistic. Independent human validation was not completed during the assignment window."
