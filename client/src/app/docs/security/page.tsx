import type { Metadata } from 'next';
import { TrustNotice } from '@/components/common/Notices';
import { A, C, Callout, DocPage, List, P, Section, StatusPill, Table } from '@/components/docs/DocsContent';
import { REPO_URL } from '@/lib/config';

export const metadata: Metadata = { title: 'Security & limitations' };

export default function SecurityGuide() {
  return (
    <DocPage href="/docs/security">
      <Section id="trust-model" title="Trust model">
        <TrustNotice />
        <P>
          AgentMesh runs models on computers owned by independent providers. Container and process isolation protect the{' '}
          <em>provider&apos;s</em> machine from the workload; they do not protect the workload from the provider. A provider can read the model files,
          the process memory, and every prompt and response their node handles. Confidential computing (hardware-isolated nodes with attestation) is
          not implemented.
        </P>
        <P>Use community nodes only for data you would be comfortable sharing with a stranger.</P>
      </Section>

      <Section id="data" title="What data is stored">
        <Table
          head={['Data', 'Stored?']}
          rows={[
            ['Prompts and responses sent to your deployments', 'No. They are not stored or logged by AgentMesh (they do pass through the provider’s machine).'],
            ['AI deployment agent requests', 'Your request text, plan and events for 90 days after the run finishes; model outputs for 24 hours. You can delete a finished run at any time. The agent’s model is Google’s Gemini API by default, so this content is sent to Google to generate answers.'],
            ['Per-request usage', 'Yes, for 400 days: endpoint, status, duration, request and response sizes, token counts and a request id.'],
            ['API keys, refresh tokens and node credentials', 'Only as hashes. API keys are shown once.'],
            ['Passwords', 'Only as Argon2id hashes.'],
            ['Two-factor secrets', 'Encrypted (AES-256-GCM), bound to your account.'],
            ['Sign-in sessions', 'IP address and browser for each session, deleted when the session expires (14 days at most).'],
            ['Bank accounts (providers)', 'Only the last four digits; Paystack holds the rest.'],
            ['Paystack webhook payloads', 'No. They contain customer contact and card details.'],
            ['Provider hardware', 'CPU model and cores, RAM, free disk, OS, architecture, GPU model and VRAM. Public statistics show counts only.'],
          ]}
        />
        <P>
          Logs redact API keys, node credentials, bearer tokens and Paystack keys, and tests check that prompts, outputs and credentials never
          appear in them, including on error paths.
        </P>
      </Section>

      <Section id="retention" title="Retention and deletion">
        <Table
          head={['Data', 'Kept for', 'Setting']}
          rows={[
            ['AI agent model outputs', '24 hours', <C key="1">AI_INFERENCE_RESULT_RETENTION_HOURS</C>],
            ['Finished AI agent runs (request, plan, events)', '90 days', <C key="2">AI_RUN_RETENTION_DAYS</C>],
            ['Per-request usage records', '400 days', <C key="3">USAGE_RECORD_RETENTION_DAYS</C>],
            ['Deployment events', '180 days', <C key="4">DEPLOYMENT_EVENT_RETENTION_DAYS</C>],
            ['Audit log', '365 days', <C key="5">AUDIT_LOG_RETENTION_DAYS</C>],
            ['Charges, ledger, payments, refunds, payouts', 'Kept (financial records)', '—'],
          ]}
        />
        <P>
          A background job deletes expired data hourly. Deleting a finished AI run (<C>DELETE /ai/deployments/&#123;id&#125;</C>) removes it from the live
          database at once and reports what was deleted; copies in database backups disappear when those backups expire.
        </P>
      </Section>

      <Section id="worker-safety" title="Worker safety for providers">
        <List
          items={[
            'The worker only accepts “deploy an approved model with these limits” and “stop” from the control plane, and validates both. It never runs customer commands.',
            'Every command carries an Ed25519 signature bound to your node, that command, its exact payload (model, digest, limits), an expiry and a single-use nonce. The worker pins the control plane’s key at enrollment and refuses anything unsigned, altered, expired, replayed or addressed to another node.',
            'The worker proves it holds the private key generated on your machine at enrollment to get one-hour sessions; the enrollment credential alone is not enough once legacy mode is off.',
            'Model weights come only from allowed hosts (Ollama registry, Hugging Face), pinned to exact versions and checked by digest; every redirect is checked.',
            'Workloads use their own ports, model directories and processes; your own Ollama install is never used or modified.',
            'On Linux, each workload runs in a systemd user scope with hard memory and CPU limits. On macOS limits are advisory.',
            'Signed self-updates accept only releases signed with the operator’s offline key, so a compromised control plane cannot push code.',
            <>The Docker worker needs the Docker socket, which is <strong>root-equivalent</strong> on the host. Prefer rootless Docker on a dedicated machine.</>,
          ]}
        />
      </Section>

      <Section id="controls" title="Platform controls">
        <List
          items={[
            'Login and registration are rate limited per client address and per email; client addresses come only from the configured proxy (FORWARDED_ALLOW_IPS).',
            'Access tokens last 15 minutes and belong to a server-side session: signing out ends it everywhere at once. Refresh tokens work once; reusing one ends the whole session.',
            'Operators and admins must use a TOTP authenticator app; without it, no operator feature or other customer’s data is reachable.',
            'Operators can quarantine a node instantly (no authentication, tunnel closed, deployments moved) and release it later. Open tunnels re-check their node every 15 seconds, so a revoked or quarantined node is cut off within 15 seconds even if the disconnect message is lost.',
            'Production startup refuses insecure settings: weak SECRET_KEY, wildcard CORS, non-https public URL, or an unapproved live Paystack key.',
            'Security headers on the API and dashboard (nosniff, frame denial, referrer policy, HSTS). The dashboard’s Content-Security-Policy lets it load scripts only from itself and send data only to itself and the API.',
            'Unset ENVIRONMENT counts as production, so a forgotten setting cannot run with development defaults.',
            'Paystack webhooks are checked with an HMAC-SHA512 signature in constant time, processed once, and credited only on matching amount and currency.',
            'All balance changes go through ledger entries with idempotency keys; reconciliation checks balances against the ledger.',
            'The dashboard redirects to checkout only on Paystack’s own domain.',
            'Token counts reported by provider machines are treated as claims: billable output tokens are capped by the response bytes and input tokens by the request size the gateway counted itself. Operators see providers whose claims exceed what was observed.',
            'CI pins every action to a commit SHA and runs dependency, secret, static-analysis, container and configuration scans on every pull request.',
          ]}
        />
      </Section>

      <Section id="risks" title="Known risks">
        <P>These are recorded in the project&apos;s security review and are not fixed yet:</P>
        <List
          items={[
            'Token counts come from the provider’s machine. The size caps bound inflation but do not prove the provider ran the right model; signatures prove a message is intact, not that the work was done honestly.',
            'A provider could keep a broken runtime “READY”: customers see failed requests, but resource time is still charged until an operator refunds it.',
            'Tokens are kept in the browser’s localStorage. The CSP limits where an injected script could send them, but it still allows inline scripts.',
            'Workload containers run as the image’s default user (root for the Ollama image), and GPU deployments see every GPU on the machine.',
            'Per-email login throttling lets someone who knows your address delay your sign-in by up to a minute.',
            'Customer balances can go below zero by up to one billing interval before deployments stop.',
            'The audit log is not tamper-evident, and secrets live in environment variables rather than a secret manager.',
          ]}
        />
      </Section>

      <Section id="not-verified" title="Not yet verified">
        <Table
          head={['Feature', 'Status', 'Detail']}
          rows={[
            ['Paystack payments and payouts', <StatusPill key="1" status="test-mode" />, 'Built against Paystack’s documented API and tested against a stand-in; not yet run against Paystack itself.'],
            ['Live (real-money) payments', <StatusPill key="2" status="planned" />, 'Disabled unless PAYSTACK_ALLOW_LIVE=true is set after a review.'],
            ['vLLM on GPUs', <StatusPill key="3" status="unverified" />, 'Unit-tested; not run on real GPU hardware. Default image tags are unverified.'],
            ['Docker worker', <StatusPill key="4" status="unverified" />, 'Isolation tests against a real Docker daemon exist and run in CI; they were not run on the development machine (no Docker access). No GPU detection in the container.'],
            ['Installable worker on macOS', <StatusPill key="5" status="unverified" />, 'launchd service files are generated and unit-tested but not run on a Mac.'],
            ['Prebuilt worker releases', <StatusPill key="6" status="planned" />, 'The release workflow and install flow are built and the install was tested on Linux against locally served assets; no release is published yet.'],
            ['Multi-replica billing with Redis', <StatusPill key="7" status="unverified" />, 'Concurrency safety rests on database compare-and-set and transactions; tested against one MongoDB replica set, not across real replicas.'],
            ['Confidential computing', <StatusPill key="8" status="planned" />, 'Not implemented.'],
          ]}
        />
      </Section>

      <Section id="reporting" title="Reporting a vulnerability">
        <Callout tone="warning" title="Please do not open public issues for security problems">
          Report privately through GitHub&apos;s <A href={`${REPO_URL}/security/advisories/new`}>private vulnerability reporting</A>, with a description,
          steps to reproduce, and the impact. See <A href={`${REPO_URL}/blob/main/SECURITY.md`}>SECURITY.md</A>.
        </Callout>
        <P>
          Providers: if you suspect your node&apos;s credential was exposed, revoke the node in the dashboard; the worker stops its workloads and deletes
          its credentials when it learns it was revoked. Customers: revoke exposed API keys under <C>API Keys</C>.
        </P>
      </Section>
    </DocPage>
  );
}
