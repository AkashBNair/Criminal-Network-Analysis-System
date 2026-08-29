# Synthetic Criminal Case Dataset
**For SIH26189 — AI-Powered Criminal Network Analysis System**

> DISCLAIMER: All names, numbers, locations, and events in this dataset are entirely fictional, created for hackathon demonstration purposes only. No resemblance to real persons, cases, or ongoing investigations is intended.

This dataset contains 8 documents describing a fictional criminal network involving:
- A smuggling ring operating in the "North Zone"
- A financial fraud ring operating in the "South Zone"
- One bridging figure connecting both groups (the intended "AI discovery")
- One red herring (a person who appears connected but is investigatively insignificant)

Use these documents as input to your entity/relationship extraction pipeline (feed each one separately to the LLM extraction prompt).

---

## Document 1: FIR Excerpt — Case No. 2026/NZ/0142

**Police Station:** North Zone Station
**Date Filed:** 03 March 2026
**Subject:** Suspected smuggling of electronic goods

Complainant reported that a truck bearing registration number **DL 4C 7729** was intercepted near the North Zone checkpoint carrying undeclared electronic goods valued at approximately Rs. 18,00,000. The truck driver, identified as **Mohan Lal Sharma**, stated that he was hired by an individual named **Ravi Sehgal** to transport the goods from a warehouse in **Ghazipur** to a location in **Karol Bagh**. Sharma stated he had worked for Sehgal on at least four previous occasions over the past six months. Investigation revealed the warehouse in Ghazipur is registered under the name **Oberoi Trading Co.**, whose listed director is **Vikram Oberoi**. Sehgal could not be located at his registered address at the time of filing.

---

## Document 2: Call Detail Record Summary — Suspect: Ravi Sehgal

**Mobile Number:** +91-98XXX-11234
**Period Analyzed:** 01 Jan 2026 – 28 Feb 2026
**Prepared by:** Cyber Cell, North Zone

Analysis of call records for the above number shows frequent contact with the following numbers:

| Contact Number | Frequency | Registered To |
|---|---|---|
| +91-97XXX-55210 | 42 calls | Vikram Oberoi |
| +91-96XXX-88712 | 19 calls | Mohan Lal Sharma |
| +91-95XXX-30044 | 11 calls | Unknown (prepaid, no ID on record) |
| +91-99XXX-67321 | 3 calls | Priya Nair |

Notably, the number registered to **Vikram Oberoi** shows a call pattern concentrated in the 48 hours preceding each of the four prior transport runs referenced by Mohan Lal Sharma in Document 1. The unidentified prepaid number (+91-95XXX-30044) was active only during a two-week window in mid-February and has not been used since.

---

## Document 3: Witness Statement — Priya Nair

**Recorded at:** South Zone Station
**Date:** 10 March 2026
**Witness Occupation:** Accountant, Meridian Financial Services

I have worked as an accountant at Meridian Financial Services for the past three years. Around January 2026, I was introduced to a man named **Vikram Oberoi** at a business networking event in South Zone. He proposed that I assist in "structuring" a series of fund transfers for a client of his, describing it as a routine consultancy arrangement. I processed four transactions on his instruction, transferring funds from an account under the name **Oberoi Trading Co.** to an account belonging to a company called **Silverline Exports**, which I later learned is controlled by **Anil Kapoor** (no relation to any public figure of the same name). I did not know the source or purpose of these funds. I became suspicious when Mr. Oberoi asked me to backdate one of the transfer confirmation documents, which I refused to do. I have not had further contact with him since late February 2026.

---

## Document 4: Financial Transaction Log — Meridian Financial Services (Extract)

| Txn ID | Date | From Account | To Account | Amount (Rs.) | Processed By |
|---|---|---|---|---|---|
| TX-8821 | 14 Jan 2026 | Oberoi Trading Co. | Silverline Exports | 4,50,000 | Priya Nair |
| TX-8843 | 29 Jan 2026 | Oberoi Trading Co. | Silverline Exports | 6,20,000 | Priya Nair |
| TX-8901 | 11 Feb 2026 | Oberoi Trading Co. | Silverline Exports | 3,10,000 | Priya Nair |
| TX-8944 | 24 Feb 2026 | Oberoi Trading Co. | Silverline Exports | 7,80,000 | Priya Nair |
| TX-9012 | 02 Mar 2026 | Silverline Exports | Kapoor Family Trust | 12,00,000 | Anil Kapoor (self-authorized) |

Note: All transactions from Oberoi Trading Co. to Silverline Exports occurred within 3–5 days of a call between Ravi Sehgal and Vikram Oberoi, per Document 2's call pattern.

---

## Document 5: Witness Statement — Suresh Bhatia (Warehouse Security Guard)

**Recorded at:** North Zone Station
**Date:** 05 March 2026

I have worked as a security guard at the Ghazipur warehouse (Oberoi Trading Co.) for two years. I have seen Mr. Vikram Oberoi visit the premises regularly, usually on Tuesdays and Fridays. I have also seen a man I now know to be **Ravi Sehgal** visit approximately twice a month, always arriving in a silver sedan. On one occasion in February, I overheard part of a conversation between Mr. Oberoi and Mr. Sehgal in which Mr. Oberoi mentioned "the South Zone contact will handle the paperwork side." I did not understand the context at the time. I have never seen a woman matching the description of Priya Nair at the warehouse. I have seen **Anil Kapoor** visit the warehouse on one occasion, in early February, for what appeared to be a brief meeting with Mr. Oberoi alone.

---

## Document 6: FIR Excerpt — Case No. 2026/SZ/0089 (Unrelated Complaint — Red Herring)

**Police Station:** South Zone Station
**Date Filed:** 18 February 2026
**Subject:** Complaint regarding delayed loan repayment

Complainant **Deepak Malhotra** filed a complaint against **Anil Kapoor** alleging non-repayment of a personal loan of Rs. 2,00,000 extended in October 2025. Mr. Malhotra stated that he had known Mr. Kapoor socially for over five years through a local badminton club and had extended the loan as a personal favor. Mr. Kapoor was reported to have partially repaid Rs. 50,000 in December 2025 but has since been unresponsive. No evidence was found linking Mr. Malhotra to any other individual or entity referenced in Cases 2026/NZ/0142 or related financial investigations. Mr. Malhotra stated he has never met Vikram Oberoi, Ravi Sehgal, or Priya Nair, and has no known business dealings beyond the personal loan dispute.

*(Note: This document is intentionally included as a "red herring" — Anil Kapoor appears here, creating a tempting but ultimately low-value connection for the network analysis to correctly deprioritize, since Deepak Malhotra has no substantive links to the rest of the network.)*

---

## Document 7: Surveillance Log Summary — Silverline Exports Office, South Zone

**Surveillance Period:** 20 Feb 2026 – 27 Feb 2026
**Prepared by:** Surveillance Unit, South Zone

Over the observed period, the following individuals were seen entering/exiting the Silverline Exports office:

- **Anil Kapoor** — daily, consistent with regular business operation
- **Vikram Oberoi** — 2 visits (22 Feb, 26 Feb), each approximately 45 minutes
- **Unidentified male, approx. 30–35 years** — 1 visit (24 Feb), arrived with Vikram Oberoi, left separately 20 minutes later. Description partially matches Ravi Sehgal per DMV photo comparison (unconfirmed).
- **Priya Nair** — no visits recorded during this period, consistent with her statement that contact ended in late February.

---

## Document 8: Bank Alert — Suspicious Activity Report (SAR), Kapoor Family Trust Account

**Filed by:** Compliance Officer, Union National Bank
**Date:** 04 March 2026

An automated compliance alert was triggered on the Kapoor Family Trust account due to a large incoming transfer (Rs. 12,00,000, Txn ID TX-9012, see Document 4) followed by three rapid partial withdrawals totaling Rs. 9,50,000 within 72 hours, each just under the Rs. 10,00,000 regulatory reporting threshold when combined with prior activity. The account is held jointly by **Anil Kapoor** and a secondary signatory listed only as **"V.O."** — full name not yet confirmed by the bank's KYC records, but flagged for further verification given the initials' partial match to Vikram Oberoi.

---

## Summary: Intended Network Structure

This is the "ground truth" your system should ideally surface, useful for validating your extraction pipeline and centrality analysis:

**Kingpin / bridging node:** Vikram Oberoi — connects the smuggling ring (North Zone) to the financial fraud ring (South Zone). Should score highest on betweenness centrality.

**Smuggling ring (North Zone):**
- Vikram Oberoi (Oberoi Trading Co.)
- Ravi Sehgal (coordinator/fixer)
- Mohan Lal Sharma (driver)
- Suresh Bhatia (witness only, not a suspect)

**Financial fraud ring (South Zone):**
- Vikram Oberoi (same individual — the bridge)
- Anil Kapoor (Silverline Exports / Kapoor Family Trust)
- Priya Nair (accountant, likely unwitting participant — good test case for "flagged but explainably low-intent")

**Red herring (should be correctly de-prioritized by your system):**
- Deepak Malhotra — connects only to Anil Kapoor, and only via an unrelated personal loan dispute with no financial/logistics overlap with the rest of the network. A good system should NOT rank him as significant despite being connected to a "central" node.

**Unresolved/ambiguous thread (good for demo nuance):**
- The unidentified prepaid number in Document 2
- The "V.O." secondary signatory in Document 8 (implies Vikram Oberoi but not fully confirmed — good example of an "investigative lead" your system should flag as requiring human verification, not an automatic conclusion)
