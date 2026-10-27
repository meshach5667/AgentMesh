import type { Metadata } from 'next';
import { A, C, Callout, Code, DocPage, List, P, Section, Table } from '@/components/docs/DocsContent';
import { API_URL, DASHBOARD_URL, REPO_URL } from '@/lib/config';

export const metadata: Metadata = { title: 'Operators & self-hosting' };

export default function OperatorGuide() {
  return (
    <DocPage href="/docs/operators">
      <Section id="hosted-vs-self" title="Hosted vs. your own instance">
        <Table
          head={['', 'Hosted AgentMesh', 'Your own instance']}
          rows={[
            ['Dashboard', <A key="d" href={DASHBOARD_URL}>{DASHBOARD_URL.replace('https://', '')}</A>, 'Wherever you deploy client/ (for example Vercel)'],
            ['API', <C key="a">{API_URL}</C>, <>Your host, e.g. <C>https://api.example.com/api/v1</C></>],
            ['Operators', 'Run by the AgentMesh maintainers', 'You'],
            ['Accounts, nodes, money', 'Shared hosted network', 'Completely separate; nothing is shared with the hosted network'],
          ]}
        />
        <P>
          The operator dashboard (<C>/operator</C>) works the same on both. The rest of this page is for people running their own instance from the{' '}
          <A href={REPO_URL}>source repository</A>.
        </P>
      </Section>

      <Section id="configuration" title="Configuration">
        <P>
          The API reads environment variables (or a <C>.env</C> file in the repository root). Anything other than{' '}
          <C>ENVIRONMENT=dev|development|test|testing</C>, including leaving it unset, counts as production, and then the API refuses to start
          unless:
        </P>
        <List
          items={[
            <><C>SECRET_KEY</C> is random and at least 32 characters (<C>openssl rand -hex 32</C>);</>,
            <><C>CORS_ORIGINS</C> lists explicit origins (JSON array or comma-separated; no <C>*</C>);</>,
            <><C>PUBLIC_BASE_URL</C> uses <C>https://</C>;</>,
            <><C>PAYSTACK_SECRET_KEY</C>, if set, is a test key, unless <C>PAYSTACK_ALLOW_LIVE=true</C>.</>,
          ]}
        />
        <Table
          head={['Variable', 'Purpose']}
          rows={[
            [<><C>MONGODB_URL</C>, <C>MONGODB_DB</C></>, <>MongoDB connection string (for example from MongoDB Atlas) and database name (default <C>agentmesh</C>). It must be a replica set, which Atlas always is: ledger postings are saved in multi-document transactions. Required outside development.</>],
            [<C key="2">SECRET_KEY</C>, 'Root of the purpose-specific keys (session tokens, MFA challenges, sponsored-view tokens, command signing unless set separately, MFA-secret encryption unless set separately). Changing it signs everyone out and rotates the command-signing key; see docs/security/INCIDENT_RESPONSE.md before rotating.'],
            [<C key="2b">FORWARDED_ALLOW_IPS</C>, 'Proxy addresses (IPs or CIDRs) whose X-Forwarded-For is trusted for client addresses. Set it to your platform’s proxy range; never * when the API port is reachable directly.'],
            [<><C>STAFF_MFA_REQUIRED</C>, <C>DATA_ENCRYPTION_KEY</C></>, 'Operators and admins must use TOTP (default on). Optional dedicated base64 32-byte key for MFA secrets at rest.'],
            [<><C>ALLOW_LEGACY_NODE_CREDENTIALS</C></>, 'Accept workers older than node sessions (default on). Turn off once every worker is upgraded.'],
            [<><C>COMMAND_SIGNING_KEY</C>, <C>COMMAND_SIGNING_PREVIOUS_KEY</C></>, 'Optional explicit Ed25519 seeds for signed commands; rotate by moving the current one to PREVIOUS.'],
            [<><C>AI_RUN_RETENTION_DAYS</C>, <C>USAGE_RECORD_RETENTION_DAYS</C>, <C>AUDIT_LOG_RETENTION_DAYS</C> and others</>, 'Retention per data class (see Security & limitations).'],
            [<><C>PUBLIC_BASE_URL</C>, <C>FRONTEND_URL</C></>, 'Public https URLs of the API and the dashboard. Paystack returns customers to $FRONTEND_URL/customer/wallet.'],
            [<C key="4">CORS_ORIGINS</C>, 'Dashboard origins allowed to call the API.'],
            [<><C>COORDINATION_BACKEND=redis</C>, <C>REDIS_URL</C></>, 'Needed only for more than one API replica. Use a password-protected Redis that is not reachable from the internet: replicas trust its messages.'],
            [<C key="6">BILLING_CURRENCY</C>, 'One platform currency (default NGN). Choose it before taking payments.'],
            [<><C>PAYSTACK_SECRET_KEY</C>, <C>PAYSTACK_WEBHOOK_IPS</C></>, 'Payments; empty key disables them.'],
            [<C key="8">METRICS_TOKEN</C>, 'Bearer token for GET /metrics; empty disables it.'],
            [<C key="10">NEXT_PUBLIC_API_URL</C>, 'Dashboard build setting: your API’s /api/v1 URL. Baked in at build time.'],
          ]}
        />
        <P>
          <C>.env.example</C> lists the minimum set. Billing intervals, payment limits and rate limits have sensible defaults; see{' '}
          <C>server/app/core/config.py</C> for every setting.
        </P>
      </Section>

      <Section id="deploy" title="Deploy">
        <P>Either run the whole stack with Docker Compose:</P>
        <Code
          code={`git clone ${REPO_URL}.git && cd AgentMeshh
export SECRET_KEY=$(openssl rand -hex 32)
export PUBLIC_BASE_URL=https://api.example.com FRONTEND_URL=https://app.example.com
docker compose up -d`}
        />
        <P>
          or deploy the parts separately: the API from <C>Dockerfile.server</C> (or <C>uvicorn app.main:app</C> in <C>server/</C>) on any host with
          MongoDB access, and the dashboard from <C>client/</C> on Vercel with <C>NEXT_PUBLIC_API_URL</C> set. Put the API behind TLS, run uvicorn with{' '}
          <C>--proxy-headers</C>, and restrict <C>--forwarded-allow-ips</C> to your proxy. The Compose stack&apos;s MongoDB is reachable only
          from the API container.
        </P>
      </Section>

      <Section id="database" title="Database">
        <P>
          AgentMesh stores everything in MongoDB. When the API starts, it creates any missing collections and indexes and adds the built-in
          model catalog entries that are missing; it never changes or removes existing data, so several replicas can start at once. There are no
          migrations to run. For local development, run <C>mongod --replSet rs0</C> once with <C>rs.initiate()</C>, or use{' '}
          <C>docker compose up -d mongo</C>.
        </P>
      </Section>

      <Section id="first-operator" title="First operator">
        <P>Operators cannot self-register. On a machine with the same <C>MONGODB_URL</C> as the API (for example your host&apos;s shell):</P>
        <Code
          code={`cd server
python scripts/create_operator.py ops@example.com              # prompts for a password (12+ characters)
python scripts/create_operator.py lead@example.com --role admin`}
        />
        <P>
          Running it for an existing account promotes that account. Each use is recorded in the audit log as <C>user.operator_provisioned</C>.
          Operator accounts have no multi-factor authentication yet; protect them carefully.
        </P>
      </Section>

      <Section id="catalog" title="Model catalog">
        <P>
          Under <strong>Model Catalog</strong>, approve models and enable or disable their artifacts (one per runtime). New catalog entries start
          unapproved. Adding an artifact, which needs a pinned source (an Ollama tag, or a Hugging Face commit and, for llama.cpp, a file SHA-256),
          is done with <C>POST /models/&#123;id&#125;/artifacts</C>; there is no dashboard form for it yet.
        </P>
      </Section>

      <Section id="pricing" title="Pricing">
        <P>
          Under <strong>Pricing</strong>, publish an immutable price version, effective now or later: CPU core-hour, memory GB-hour, GPU-memory
          GB-hour, input and output tokens per million, and the platform commission. Until a price list exists, usage is measured but not charged. You
          can set token prices to zero to charge for resources only.
        </P>
        <P>
          The commission is the share of each charge the platform keeps; the provider whose node served the deployment is credited the rest.
          A version published without a rate gets <C>DEFAULT_PLATFORM_FEE_RATE</C> (10%), and no version may exceed{' '}
          <C>MAX_PLATFORM_FEE_RATE</C> (50%). To change only the commission, use <strong>Change commission</strong> (or{' '}
          <C>POST /admin/commission</C>): it publishes a version with the prices in force. Every charge keeps the rate it was split at, so
          past earnings never change. The fee is rounded to the ledger&apos;s precision and the provider gets exactly the rest, so commission
          plus provider share always equals what the customer paid. Only READY time and successful requests are charged.
        </P>
      </Section>

      <Section id="paystack" title="Payments (Paystack)">
        <Callout tone="warning" title="Test mode only">
          AgentMesh uses Paystack test mode unless a live key is explicitly allowed. It has been verified against a stand-in for Paystack&apos;s
          API but not against Paystack itself. Run the smoke script below before relying on it.
        </Callout>
        <List
          ordered
          items={[
            <>In the Paystack dashboard (test mode), copy the secret key into <C>PAYSTACK_SECRET_KEY</C> and set the webhook URL to <C>https://&lt;your-api&gt;/api/v1/payments/paystack/webhook</C>.</>,
            <>Check the integration against Paystack&apos;s real test API: <C>PAYSTACK_SECRET_KEY=sk_test_... python scripts/paystack_smoke.py</C> (add <C>--pay</C> to pay with a test card).</>,
            'Make a top-up from the dashboard and confirm that the webhook arrives: Reconciliation should show no open top-ups, and Ledger should show the deposit.',
            <>Payouts use Paystack Transfers: they need a funded balance and transfer OTP turned off, or they stop at <C>OTP_REQUIRED</C>.</>,
          ]}
        />
        <P>
          Top-ups are credited once, only after Paystack reports success with a matching amount and currency. Payouts are held at request time and
          need operator approval (<strong>Payouts</strong>). Reconciliation runs every 10 minutes when payments are enabled.
        </P>
      </Section>

      <Section id="revenue" title="Revenue analytics">
        <P>
          <strong>Revenue</strong> charts, per day for the last 7, 30 or 90 days, what customers paid, split into the provider share and the
          commission, together with refunds, top-ups, payouts and card refunds. <strong>Platform revenue</strong> is the commission net of reversed
          fees, plus sponsorship revenue, which is shown as a separate figure. Every number is computed by the server from rated charges, refunds and
          payments; nothing is estimated. The same data is available at <C>GET /analytics/revenue?scope=network&amp;days=30</C>.
        </P>
      </Section>

      <Section id="refunds" title="Refunds">
        <List
          items={[
            <>A <strong>compute charge</strong> refund (full or partial) credits the customer&apos;s wallet. The provider share and the commission are reversed in the same proportions as the original split (<C>REFUND_CLAWBACK</C> and <C>PLATFORM_FEE_REVERSAL</C> ledger entries). A provider who was already paid out can go negative; later earnings cover it.</>,
            <>A <strong>top-up</strong> refund returns unspent wallet funds to the customer&apos;s card through Paystack. The amount is held at once; the refund settles when Paystack reports it processed (webhook or reconciliation) and the hold is released if it fails. Only one card refund per top-up can be open at a time.</>,
            'Each refund needs a reason, which the customer sees. Refunds are audited and checked by reconciliation; a charge can never be refunded beyond what was paid.',
          ]}
        />
      </Section>

      <Section id="sponsorships" title="Sponsorships">
        <P>
          Sponsored placements are optional and <strong>off by default</strong>. Under <strong>Sponsorships</strong>, turn advertising on, choose
          which placements show items (landing page, docs, customer and provider dashboards, 1 to 3 items each) and manage campaigns for AI tools,
          GPU hardware and infrastructure providers. Campaigns start as drafts; drafts can be activated, active campaigns paused and resumed, and
          any campaign ended (final). A campaign is served only while active, inside its schedule and under its budget.
        </P>
        <P>
          Items are labelled &ldquo;Sponsored&rdquo;, link only to the campaign&apos;s stored https URL with <C>rel=&quot;sponsored&quot;</C>, and can
          be dismissed by viewers. Impressions count once per signed view token when at least half the item is visible; clicks count once per view.
          No personal data is used to select items, and no third-party ad scripts are loaded. Pricing is CPM, CPC or a flat fee; earnings are reported
          on the Revenue page separately from compute commission.
        </P>
      </Section>

      <Section id="monitoring" title="Monitoring">
        <Table
          head={['Endpoint', 'Use']}
          rows={[
            [<C key="1">GET /health</C>, 'Liveness.'],
            [<C key="2">GET /health/ready</C>, 'Database (and Redis) readiness; 503 if either fails. Use for load balancers.'],
            [<C key="3">GET /metrics</C>, <>Prometheus, with <C>Authorization: Bearer $METRICS_TOKEN</C>.</>],
            [<C key="4">GET /api/v1/admin/overview</C>, 'Operator dashboard figures, including nodes with overdue heartbeats.'],
            [<C key="5">GET /api/v1/admin/reconciliation</C>, 'Ledger invariants and open payment items.'],
            [<C key="6">GET /api/v1/admin/anomalies</C>, 'Providers whose token claims exceed the request and response sizes the gateway observed, or whose requests mostly fail.'],
            [<C key="7">POST /api/v1/admin/nodes/&#123;id&#125;/quarantine</C>, 'Cut a node off at once (no authentication, tunnel closed, deployments moved); release with /release. See docs/security/INCIDENT_RESPONSE.md.'],
          ]}
        />
        <P>
          Logs are JSON lines with a request id; API keys, node credentials, bearer tokens and Paystack keys are redacted, and security events
          (session refusals, closed tunnels, rejected commands) are logged with an allowlist of fields under <C>agentmesh.security</C>. Alert on readiness
          failing, rising 5xx, payouts stuck <C>PENDING</C> or <C>OTP_REQUIRED</C>, reconciliation reporting <C>ok: false</C>, and{' '}
          <C>Background job … failed</C> in the logs.
        </P>
      </Section>

      <Section id="backups" title="Backups and recovery">
        <Code
          code={`cd server
MONGODB_URL=mongodb+srv://… KEEP=14 ops/backup_db.sh /var/backups/agentmesh
MONGODB_URL=mongodb+srv://… MONGODB_DB=agentmesh_restore ops/restore_db.sh /var/backups/agentmesh/agentmesh-<ts>.archive.gz`}
        />
        <List
          items={[
            'Backups are compressed mongodump archives (mode 0600). On Atlas, also enable its scheduled backups. Store copies off the host, encrypted, and test a restore monthly. The restore script refuses a non-empty database.',
            'After a restore: point MONGODB_DB at it, start the API, then run reconciliation to re-check open top-ups and payouts with Paystack.',
            'API restarts lose nothing: workers reconnect and billing resumes from each deployment’s watermark without double charging.',
            'Never refund a pending payout by hand; the transfer may still complete. Refund customers from Refunds, which reverses the provider share and commission through the ledger.',
            <>Incident runbooks (compromised nodes, leaked credentials, key rotation, rollback) are in <A href={`${REPO_URL}/blob/main/docs/security/INCIDENT_RESPONSE.md`}>docs/security/INCIDENT_RESPONSE.md</A>.</>,
          ]}
        />
      </Section>

      <Section id="worker-releases" title="Publishing worker releases">
        <List
          ordered
          items={[
            <>Set <C>WORKER_VERSION</C> in <C>server/node_agent/config.py</C>, and <C>WORKER_VERSION</C> in <C>client/src/lib/config.ts</C> to match (a test checks this).</>,
            <>Commit, then tag and push: <C>git tag worker-v0.3.0 && git push origin worker-v0.3.0</C>.</>,
            <>The <C>Worker release</C> workflow checks the tag matches, builds the wheel, checks it installs, writes <C>SHA256SUMS</C>, and creates the GitHub release with the wheel, <C>install.sh</C>, <C>uninstall.sh</C> and <C>SHA256SUMS</C>.</>,
            'Redeploy the dashboard so Add a machine points at the new version.',
          ]}
        />
        <Callout tone="warning" title="The repository must be public">
          Providers download release assets anonymously, so the GitHub repository (or at least its releases) must be publicly readable.
        </Callout>
        <P>
          Signed self-updates are a separate, optional channel: sign a release manifest with <C>scripts/sign_worker_release.py</C> using an Ed25519 key
          kept offline, and point <C>WORKER_RELEASE_DIR</C> at the output. Never add that private key to GitHub Actions or the control plane.
        </P>
      </Section>
    </DocPage>
  );
}
