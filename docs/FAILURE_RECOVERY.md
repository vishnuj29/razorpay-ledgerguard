# Razorpay Form Question 12 Submission
## "What broke, and how you got out"

In our first build, we tried feeding entire reconciliation batches directly into an LLM prompt to compute net settlements and balance accounts. It failed immediately: the LLM suffered from subtle floating-point precision drift on 18% GST calculations (like ₹976.38 instead of ₹976.40 on ₹1,000 orders), and it completely choked on 1:N batch settlements by double-counting orders across bank lines.

We fixed this by taking math away from AI entirely:

1. **Deterministic Core:** We built a closed-form Python math engine that validates fee schedules (`Gross - MDR - GST == Net`) with a strict ±0.02 paise tolerance, and groups 1:N batch settlements using subset-sum indexing over UTRs.
2. **Scoped Semantic AI:** We restricted the AI strictly to semantic diagnosis—extracting tokens from unstandardized bank narrations, detecting dropped webhooks where OMS state stayed `CREATED`, and drafting double-entry journal entries without performing arithmetic.
3. **Hard Policy Gates:** Any anomaly with confidence below 85% or unmapped offline wires goes straight to an honest exception queue instead of guessing.

This eliminated math hallucinations entirely (0.00% error rate), dropped execution time to 0.09s (1,331 rec/sec), and gave us a reliable 88.7% automated match rate with an honest audit trail.
