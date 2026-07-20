# Architecture

_Last updated: [DATE]

**Status: Planning phase — no code has been written yet.** Everything in
this document describes the intended design, not an implemented system.
Treat every step, decision, and "resolved" label as a plan to be validated
during implementation, not a description of working behavior. Update this
note once implementation begins.



## Overview

This project is an email intelligence service. Given an advisor's mailbox and a client's (household's) email address, it retrieves the relevant historical correspondence, filters and groups it, and compresses the content, and outputs structured data suitable for LLM prompting.

See the diagram below for the full data flow, and the numbered steps for the implementation-level detail.


## ⚠️ Current integration status: Mocked

See [`docs/graph-api-integration.md`](./graph-api-integration.md) for full detail. Short version: this project currently runs against a **Mockoon** simulation of the Microsoft Graph API, not the live API.


## Identity model (For myself)

This service involves **two distinct identities**:

- **Advisor mailbox**: the actual Outlook/Graph mailbox being queried. This is what the service authenticates against.
- **ClientID**: the client/household's email address. This is not a mailbox the service accesses directly, it is an identifier used to **filter** for relevant messages **within** the advisor's mailbox. Furthermore, this is identifier is shared across various other platforms.

**Request Scope**: Currently supports for one request = one advisor mailbox + one `ClientID`. Would add the feature for multiple clients once MVP is working.

---

## Diagram

[ADD DIAGRAM HERE]

---

## Data Flow

1. Request comes in with: an advisor mailbox identity, and a single client ID.
2. Authenticate/query against the **advisor credentials**.
3. Search the advisor's mailbox for all messages over a 3 to 5 yrs window where the client id appears (From/To/Cc).
4. Group the matched messages by subject.
5. For each subject group, take the **most recent email**.
6. Determine whether the latest email in the subject group is **modified** or **unmodified**:

  - **Unmodified:** (still contains full quoted/trailing history), this is detected via presence of quote markers such as  `>`[ "On [date], X wrote:"]-> no further API calls necessary.

  - **Modified:** (quote markers absent) -> fetch the full history via `conversationId`. Since a single `conversationId` can span **multiple threads** (Graph API does not guarantee one thread = one conversation, especially if participants change or messages get split) this means fetching all threads under that conversationId and merging chronologically ordering the resulting messages.

7. For each email in the resolved thread: extract the body (via HTML scraper) and attachments if present.

8. Compress the body only, using a hybrid approach: rule-based compression first, followed by LLMLingua. Attachments are preserved but not compressed or fed into the LLM pipeline(attachment types vary too much to handle reliably in the MVP).

9. Output a structured JSON object metadata + compressed_body + ClientID(email) so downstream consumers know which household (client) the record belongs to.
