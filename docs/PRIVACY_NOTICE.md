# AgentMesh Privacy Notice

**Status:** Draft, pending legal review
**Effective date:** 26 October 2026
**Last updated:** 26 October 2026

## 1. About This Notice

This notice explains how AgentMesh ("AgentMesh", "we", "us") collects, uses, shares and protects information when you use the AgentMesh platform, whether as a customer deploying and calling AI models or as a provider contributing compute.

AgentMesh is operated by Obed Meshach. Questions about this notice can be sent to meshachzakumi@gmail.com.

## 2. How AgentMesh Works, and Why It Matters for Your Privacy

AgentMesh runs open-weight AI models on machines operated by independent third-party providers. To serve your requests, the provider's machine assigned to your deployment must process your prompts and the generated outputs in readable (unencrypted) form.

We encrypt data in transit with HTTPS, our database provider encrypts stored data at rest, and we apply technical controls to limit what providers can access:
- providers never receive your name, email address, account identity or billing details;
- every instruction sent to a provider's machine is signed and bound to that machine;
- providers can be cut off within seconds.

However, **standard community-node execution does not prevent a provider, or anyone who has compromised a provider's machine, from inspecting data processed on that machine.** Providers are independent operators, not AgentMesh employees, and may be located in any country.

**Do not submit** passwords, private keys, access tokens, financial account details, health information, government identification numbers, confidential business documents, or other sensitive or regulated information to community nodes unless you have assessed and accepted this risk.

If we later offer execution options with stronger confidentiality protections, we will describe them separately and offer them only once the relevant technical protections have been implemented and validated.

## 3. Information We Collect

**Account information.** Your email address, your password (stored only as an Argon2id hash), your account role, and, if you turn on two-factor authentication, its secret (stored encrypted). For providers who request payouts: the bank, account name and last four digits of the payout account. Paystack holds the full account number.

**Requests you send to your deployments.** Prompts and generated outputs pass through AgentMesh to the provider's machine and back. **We do not store them or write them to our logs.**

**AI deployment assistant.** If you use the assistant that plans deployments for you, we store your request text, the plan and the steps taken, and briefly the model's replies (see Section 7). The assistant is powered by Google's Gemini API, so this content is sent to Google to generate its answers (see Section 5).

**Usage and billing records.** Request identifiers, timestamps, the deployment and model used, request and response sizes, token counts reported by the provider's machine, request outcome, resource time, charges, refunds, top-ups and payouts. Card payments are handled by Paystack; card details never reach AgentMesh.

**Provider node information.** Node name, region you declare, hardware (CPU model and cores, memory, free disk, operating system, GPU model and memory), software versions, availability, performance metrics and job history. The public marketplace shows node name, region and hardware; public statistics show only counts.

**Security and technical data.** The IP address and browser identification (user agent) of each sign-in session, authentication events (including failed sign-ins and the email entered), and records of administrative actions. These are used to operate and protect the service.

**In your browser.** The dashboard stores your sign-in tokens, your theme preference and sponsored items you dismissed in your browser's local storage. We use no advertising or analytics trackers. Sponsored items, when shown, are chosen without using your personal data and are counted anonymously.

## 4. How We Use Information

We use information to:
- provide the service, including placing deployments on providers' machines and relaying requests and results;
- authenticate users and machines, and enforce access controls;
- calculate usage, bill customers, pay providers and process refunds;
- detect, investigate and prevent fraud, abuse and security incidents, including checking providers' reported usage against what our servers observe;
- resolve disputes and provide support;
- maintain and improve the reliability and performance of the platform, using aggregated operational data;
- comply with legal obligations.

**We do not use your prompts, inputs or outputs to train AI models** unless you give separate, explicit, informed consent, which you may withdraw at any time. We do not currently ask for such consent. Content you give the AI deployment assistant is processed by Google under its Gemini API terms; whether Google may use it to improve its products depends on the Gemini service tier we use, as described in Section 5.

**We do not sell your personal information.**

## 5. How We Share Information

- **Providers** receive the content needed to serve your requests (prompts, the model to run and resource limits). They do not receive your name, email address, account identity or billing information from us.
- **Service providers** that host, store or process data for us:
  - Render (API hosting);
  - Vercel (dashboard hosting);
  - MongoDB Atlas (database);
  - Paystack (payments). Paystack receives your email address when you top up, and providers' bank details for payouts;
  - Google (Gemini API), which receives what you write to the AI deployment assistant, the assistant's planning conversation and short status details, to generate the assistant's answers. On Google's unpaid tier Google may use this content to improve its products; on a paid tier it does not. Requests you send to your own deployments never go to Google.

  Hugging Face receives only public model lookups, never your data.
- **Sponsors** of optional sponsored placements receive no personal information about you.
- **Legal and safety** disclosures where required by law or reasonably necessary to protect the rights, property or safety of users, providers, AgentMesh or the public.
- **Business transfers**, such as a merger or acquisition, subject to this notice or equivalent protections.

## 6. Provider Obligations

Providers must not inspect, copy, retain, log or share job content beyond what is necessary to serve assigned requests, and must not keep data after a deployment ends. Their worker software removes each deployment's runtime and working files when the deployment stops, fails or moves. Providers who breach these rules may be quarantined or removed from the network.

These are policy commitments and software defaults. They reduce risk but do not technically prevent a provider from accessing data on its own machine, as explained in Section 2.

## 7. Data Retention

| Data | Retention |
|---|---|
| Prompts and outputs sent to your deployments | Not stored by AgentMesh |
| AI deployment assistant: model replies | 24 hours |
| AI deployment assistant: your request, plan and steps | 90 days after the run finishes, or until you delete it |
| Temporary files on provider machines | Deleted when the deployment stops, fails or moves |
| Per-request usage records | 400 days |
| Charges, payments, refunds, payouts and ledger records | Kept for accounting and legal purposes |
| Deployment history (status changes) | 180 days |
| Sign-in sessions (IP address, browser) | Until the session ends, at most 14 days |
| Security and administrative audit records | 365 days |
| Account information | For the life of the account; deleted on request when the account is closed, except records we must keep by law |
| Backups | Deleted data may remain in our backup archives for up to 14 days before they are replaced |

You can delete finished AI deployment assistant runs from your account at any time. Deletion removes the data from our active systems immediately; copies in backups expire on the schedule above. Data that a provider retained in breach of its obligations is outside our technical control.

## 8. Security

Our measures include:
- encryption in transit;
- access controls on every request, with each customer's data isolated from other customers;
- short-lived sign-in sessions that end immediately when you sign out;
- two-factor authentication, required for our operators;
- per-machine identities for providers' computers, with revocation within seconds and signed instructions;
- container isolation for workloads on providers using our Docker worker;
- logs designed to exclude request content;
- security monitoring and automated security testing of our code and dependencies.

No system is completely secure, and the limitations in Section 2 apply to community-node execution. AgentMesh has not had an independent security audit.

To report a security vulnerability, see our security policy: <https://github.com/meshach5667/AgentMesh/blob/main/SECURITY.md>.

## 9. International Processing

Providers and our service providers may be located in countries other than yours, including countries with different data protection laws. When you send a request, it is processed wherever the provider assigned to your deployment is located. You can ask for a region when you create a deployment; regions are declared by providers and are not independently verified. We do not currently offer contractual data-transfer mechanisms or guaranteed data residency.

## 10. Your Rights

Depending on where you live, applicable data protection laws may give you rights to access, correct, delete, restrict or object to processing of your personal data, to receive a copy of it, and to withdraw consent. These may include the Nigeria Data Protection Act 2023 and the EU or UK GDPR. You may also have the right to complain to a data protection authority, such as the Nigeria Data Protection Commission.

To exercise these rights, contact meshachzakumi@gmail.com. We may need to verify your identity before acting on a request.

## 11. Children

AgentMesh is not intended for individuals under 18, and we do not knowingly collect their personal information.

## 12. Changes to This Notice

We will update this notice when our practices change. Material changes will be communicated through the platform or by email before they take effect.

## 13. Contact

Obed Meshach
meshachzakumi@gmail.com
