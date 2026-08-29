# Synthetic Criminal Case Dataset — Part 2
**For SIH26189 — AI-Powered Criminal Network Analysis System**

> DISCLAIMER: All names, numbers, locations, and events in this dataset are entirely fictional, created for hackathon demonstration purposes only. No resemblance to real persons, cases, or ongoing investigations is intended.

This is a second, independent batch of documents (9–16) — designed to either (a) extend the same network from Part 1, or (b) be used as a standalone demo scenario if you want a fresh dataset. Notes at the end explain how the two parts relate.

---

## Document 9: FIR Excerpt — Case No. 2026/NZ/0158

**Police Station:** North Zone Station
**Date Filed:** 15 March 2026
**Subject:** Recovery of counterfeit currency

A raid on a residential property in **Shastri Nagar** led to the recovery of counterfeit currency notes with a face value of approximately Rs. 6,40,000. The property is registered under **Farhan Qureshi**, who was detained for questioning. Qureshi stated the notes were delivered to him by a courier two days prior and that he was instructed to hold them until further notice by a person he knew only as **"Bunty."** Phone records recovered from Qureshi's device show repeated contact with a number later confirmed to be registered to **Ravi Sehgal**, who investigators believe may be the individual referred to as "Bunty."

---

## Document 10: Call Detail Record Summary — Suspect: Farhan Qureshi

**Mobile Number:** +91-93XXX-44210
**Period Analyzed:** 20 Feb 2026 – 14 Mar 2026

| Contact Number | Frequency | Registered To |
|---|---|---|
| +91-98XXX-11234 | 27 calls | Ravi Sehgal |
| +91-96XXX-88712 | 6 calls | Mohan Lal Sharma |
| +91-92XXX-70091 | 15 calls | Unknown (unregistered SIM) |

The unregistered number shows a burst of activity in the 24 hours before the Shastri Nagar raid, followed by no further activity — consistent with a "burner phone" pattern.

---

## Document 11: Witness Statement — Farhan Qureshi (Detainee Statement)

**Recorded at:** North Zone Station
**Date:** 16 March 2026

I was contacted by a man I know as Bunty around late February. He said he had "storage work" for me and would pay Rs. 15,000 for holding a package for a short period. I did not know what was inside until the police opened it during the raid. I have met Bunty in person only once, at a tea stall near the North Zone bus depot. I do not know his real name. I have never met or heard of Vikram Oberoi, Anil Kapoor, or Priya Nair. I have driven for Mohan Lal Sharma's transport business on a few occasions as an informal helper, which is likely how Bunty got my number — Sharma introduced us in passing at a dhaba around January this year.

---

## Document 12: Financial Transaction Log — Sehgal Personal Account (Extract)

| Txn ID | Date | From Account | To Account | Amount (Rs.) | Notes |
|---|---|---|---|---|---|
| TX-7710 | 18 Feb 2026 | Sehgal Personal | Qureshi Personal | 15,000 | Marked "consulting fee" |
| TX-7745 | 02 Mar 2026 | Oberoi Trading Co. | Sehgal Personal | 85,000 | Marked "transport charges" |
| TX-7802 | 09 Mar 2026 | Sehgal Personal | Unknown (cash withdrawal, ATM) | 40,000 | ATM location: Shastri Nagar branch |

---

## Document 13: Witness Statement — Tea Stall Owner, Ramesh Yadav

**Recorded at:** North Zone Station
**Date:** 17 March 2026

I run a tea stall near the North Zone bus depot. I have seen the man now identified as Ravi Sehgal at my stall many times over the past year, usually meeting different people briefly before leaving. I recall seeing him with a younger man matching the photo of Farhan Qureshi shown to me by police, sometime in late February. I also recall seeing Sehgal meet an older man in a white kurta on multiple occasions — I do not know this man's name, but he arrived each time in a black SUV with a driver. I was not asked to identify this man from any photograph.

*(Note: The "older man in a white kurta" is an intentionally unresolved thread — you may choose to leave this as an open investigative lead in your demo, showing your system correctly flags "insufficient data to identify" rather than guessing.)*

---

## Document 14: FIR Excerpt — Case No. 2026/SZ/0095

**Police Station:** South Zone Station
**Date Filed:** 20 March 2026
**Subject:** Complaint of investment fraud

Complainant **Sunita Rao** alleged she invested Rs. 5,00,000 in a scheme presented to her by **Anil Kapoor** as a "guaranteed returns export financing opportunity" through Silverline Exports. She stated she has received no returns and Kapoor has stopped responding to her calls since early March 2026. Preliminary inquiry shows at least three other individuals filed similar complaints against Silverline Exports in the past two months, though this is the first formally registered FIR. Investigators note this may indicate a broader pattern of solicitation beyond the transactions already documented in Case 2026/NZ/0142's related financial inquiry.

---

## Document 15: Call Detail Record Summary — Suspect: Anil Kapoor

**Mobile Number:** +91-97XXX-20087
**Period Analyzed:** 01 Feb 2026 – 20 Mar 2026

| Contact Number | Frequency | Registered To |
|---|---|---|
| +91-97XXX-55210 | 34 calls | Vikram Oberoi |
| +91-99XXX-67321 | 4 calls | Priya Nair |
| +91-91XXX-33456 | 8 calls | Sunita Rao |
| +91-90XXX-12098 | 6 calls | Unregistered (linked to 2 other unregistered complainant contacts) |

Investigators note the pattern of short, frequent calls to unregistered numbers in the two weeks before each new deposit was received into the Kapoor Family Trust account, suggesting a possible solicitation-to-deposit pipeline.

---

## Document 16: Internal Investigation Note — Case Coordination Memo

**Prepared by:** Joint Investigation Cell
**Date:** 22 March 2026
**Subject:** Possible linkage between Case 2026/NZ/0142, 2026/NZ/0158, and 2026/SZ/0095

This memo is prepared to flag a possible common network across three separately filed cases. Preliminary review suggests:

1. Vikram Oberoi appears as a financial link between the smuggling operation (Case 0142) and the investment fraud complaints (Case 0095) via transactions with Anil Kapoor.
2. Ravi Sehgal appears operationally connected to both the original smuggling case and the newly discovered counterfeit currency case (0158) via Farhan Qureshi.
3. Mohan Lal Sharma is a shared low-level connection between Sehgal's transport operations and Qureshi's recruitment into the counterfeit currency matter, though there is no evidence Sharma had knowledge of the counterfeit scheme itself.
4. The "older man in a white kurta" referenced in witness statement (Document 13) remains unidentified and should be treated as an open lead, not a confirmed network member.
5. Deepak Malhotra (Case 2026/SZ/0089) remains assessed as unrelated to this network based on available evidence.

Recommend consolidated investigation across all three case numbers.

---

## How Part 1 and Part 2 relate

Part 2 **extends the same network** introduced in Part 1 — it adds:
- A new sub-thread (counterfeit currency, Case 0158) connected via **Ravi Sehgal**
- A new low-level connector (**Farhan Qureshi**) recruited through **Mohan Lal Sharma**
- A new fraud complainant (**Sunita Rao**) reinforcing the **Anil Kapoor** fraud pattern from Part 1
- An intentionally **unresolved lead** ("man in white kurta") to demonstrate your system correctly handling incomplete information
- An explicit **internal memo (Document 16)** that mirrors what your AI system's own output should look like — useful as a "ground truth" reference to compare your system's auto-generated summary against.

**Recommended usage:**
- If you want a **richer, more complex demo** (better for showing off centrality/community detection across 3 linked cases), feed both Part 1 + Part 2 (16 documents total) into your pipeline.
- If you want a **simpler, faster-to-process demo** (safer for a live presentation with time constraints), Part 1 alone (8 documents) is sufficient and already has a complete, self-contained network with a kingpin, two clusters, and one red herring.

**Updated "ground truth" network summary (Part 1 + Part 2 combined):**

| Person | Role | Expected centrality |
|---|---|---|
| Vikram Oberoi | Kingpin / bridges smuggling ↔ fraud rings | Highest betweenness |
| Ravi Sehgal | Operational fixer / bridges smuggling ↔ counterfeit sub-case | High betweenness, high degree |
| Anil Kapoor | Fraud ring lead | High degree within fraud cluster |
| Mohan Lal Sharma | Low-level connector (driver, recruiter) | Moderate degree, low centrality otherwise |
| Farhan Qureshi | Peripheral / recruited low-level participant | Low centrality |
| Priya Nair | Peripheral / likely unwitting | Low centrality, flagged for "reduced culpability" nuance |
| Sunita Rao, Deepak Malhotra | Victims/complainants, not network members | Should NOT be flagged as significant |
| "Man in white kurta" | Unidentified | Should appear as an "unresolved node" — good for showing your system doesn't overclaim |
