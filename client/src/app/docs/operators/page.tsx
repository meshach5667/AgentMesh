import type { Metadata } from 'next';
import { A, C, Callout, Code, DocPage, List, P, Section, Table } from '@/components/docs/DocsContent';
import { API_URL, DASHBOARD_URL, REPO_URL } from '@/lib/config';
import { docMetadata } from '@/lib/seo';

export const metadata: Metadata = docMetadata('/docs/operators');

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
            <><C>PUBLIC_BASE_URL</C> uses <C>https://</C>.</>,
          ]}
        />
        <Table
          head={['Variable', 'Purpose']}
          rows={[
            [<><C>MONGODB_URL</C>, <C>MONGODB_DB</C></>, <>MongoDB connection string (for example from MongoDB Atlas) and database name (default <C>agentmesh</C>). It must be a replica set, which Atlas always is: placements and capacity reservations are saved in multi-document transactions. Required outside development.</>],
            [<C key="2">SECRET_KEY</C>, 'Root of the purpose-specific keys (session tokens, MFA challenges, sponsored-view tokens, command signing unless set separately, MFA-secret encryption unless set separately). Changing it signs everyone out and rotates the command-signing key; see docs/security/INCIDENT_RESPONSE.md before rotating.'],
            [<C key="2b">FORWARDED_ALLOW_IPS</C>, 'Proxy addresses (IPs or CIDRs) whose X-Forwarded-For is trusted for client addresses. Set it to your platform’s proxy range; never * when the API port is reachable directly.'],
            [<><C>STAFF_MFA_REQUIRED</C>, <C>DATA_ENCRYPTION_KEY</C></>, 'Operators and admins must use TOTP (default on). Optional dedicated base64 32-byte key for MFA secrets at rest.'],
            [<><C>ALLOW_LEGACY_NODE_CREDENTIALS</C></>, 'Accept workers older than node sessions (default on). Turn off once every worker is upgraded.'],
            [<><C>COMMAND_SIGNING_KEY</C>, <C>COMMAND_SIGNING_PREVIOUS_KEY</C></>, 'Optional explicit Ed25519 seeds for signed commands; rotate by moving the current one to PREVIOUS.'],
            [<><C>AI_RUN_RETENTION_DAYS</C>, <C>USAGE_RECORD_RETENTION_DAYS</C>, <C>AUDIT_LOG_RETENTION_DAYS</C> and others</>, 'Retention per data class (see Security & limitations).'],
            [<C key="3">PUBLIC_BASE_URL</C>, 'Public https URL of the API (deployment endpoints are built from it).'],
            [<C key="3f">FRONTEND_URL</C>, 'Public URL of the dashboard: customers return here from a provider’s gateway checkout.'],
            [<><C>CREDIT_MIN_PREPAID_HOURS</C>, <C>PAYMENT_VERIFY_WINDOW_HOURS</C></>, 'Credit needed to start on a priced machine (hours of its reservation, default 1), and how long pending gateway payments are re-checked (default 24 h).'],
            [<C key="3m">MIGRATION_DRAIN_SECONDS</C>, 'After a planned move switches traffic, how long the old copy keeps serving in-flight requests (default 120).'],
            [<C key="4">CORS_ORIGINS</C>, 'Dashboard origins allowed to call the API.'],
            [<><C>COORDINATION_BACKEND=redis</C>, <C>REDIS_URL</C></>, 'Needed only for more than one API replica. Use a password-protected Redis that is not reachable from the internet: replicas trust its messages.'],
            [<C key="6">DEFAULT_CURRENCY</C>, 'Currency of a deployment’s price limits when the customer names none (default NGN). Providers price machines in their own currency; AgentMesh processes no payments.'],
            [<><C>HEARTBEAT_DEGRADED_SECONDS</C>, <C>HEARTBEAT_TIMEOUT_SECONDS</C>, <C>NODE_RECOVERY_HEARTBEATS</C>, <C>NODE_FAILURE_THRESHOLD</C></>, 'Node health and failover; see Failover tuning below.'],
            [<C key="8">METRICS_TOKEN</C>, 'Bearer token for GET /metrics; empty disables it.'],
            [<C key="10">NEXT_PUBLIC_API_URL</C>, 'Dashboard build setting: your API’s /api/v1 URL. Baked in at build time.'],
          ]}
        />
        <P>
          <C>.env.example</C> lists the minimum set. Failover timing, cost-estimate intervals and rate limits have sensible defaults; see{' '}
          <C>server/app/core/config.py</C> for every setting.
        </P>
      </Section>

      <Section id="deploy" title="Deploy">
        <P>Either run the whole stack with Docker Compose:</P>
        <Code
          code={`git clone ${REPO_URL}.git && cd AgentMesh
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

      <Section id="business-model" title="Payments and fees">
        <P>
          AgentMesh holds no money. Providers price their own machines; customers buy prepaid credit with a provider by paying the provider
          directly, through the provider&apos;s own Paystack, Flutterwave or Stripe account (verified by AgentMesh with that account&apos;s API) or
          by transfer the provider confirms. Priced service needs verified credit, and usage draws it down. The platform has no gateway account,
          payment keys or webhooks of its own, takes no commission and charges no subscription. Providers&apos; gateway keys are encrypted at
          rest (AES-256-GCM under <C>DATA_ENCRYPTION_KEY</C>, bound to the provider) and only ever sent to the gateway&apos;s official API host.
        </P>
        <P>
          Databases upgraded from the earlier payment system keep its collections (<C>charges</C>, <C>transactions</C>, <C>wallets</C>,{' '}
          <C>payments</C>, <C>payouts</C>, <C>refunds</C>, <C>pricing_rules</C> and others) untouched as history; nothing reads or writes them, and
          they can be exported with the backup script before you decide whether to archive them.
        </P>
      </Section>

      <Section id="failover" title="Failover tuning">
        <Table
          head={['Setting (default)', 'Effect']}
          rows={[
            [<C key="1">WORKER_HEARTBEAT_INTERVAL_SECONDS (15)</C>, 'How often workers report.'],
            [<C key="2">HEARTBEAT_DEGRADED_SECONDS (45)</C>, 'A node with an older heartbeat gets no new work, but nothing is moved: one slow heartbeat is not a failure.'],
            [<C key="3">HEARTBEAT_TIMEOUT_SECONDS (90)</C>, 'A node silent this long is OFFLINE: work still starting there moves at once, serving work after UNHEALTHY_GRACE_SECONDS (180).'],
            [<C key="4">NODE_RECOVERY_HEARTBEATS (2)</C>, 'Healthy heartbeats a node needs after an outage before it gets new work.'],
            [<C key="5">NODE_FAILURE_THRESHOLD (3), NODE_DEGRADED_COOLDOWN_SECONDS (600)</C>, 'Failed placements in a row that bench a node, and for how long.'],
            [<C key="6">MAX_SCHEDULE_ATTEMPTS (5)</C>, 'Placements per deployment, including the first.'],
            [<C key="7">PLACEMENT_RETRY_BASE_SECONDS (15), PLACEMENT_RETRY_MAX_SECONDS (300), PLACEMENT_PENDING_MAX_SECONDS (3600)</C>, 'Backoff (with ±20% jitter) for deployments waiting for a node, and how long they may wait before failing.'],
          ]}
        />
        <P>
          Placement state is persisted, so restarts lose nothing: the monitor (one leader among replicas) resumes pending placements, and each is
          claimed with a compare-and-set before it is placed. Reservations and attempts allow one active row per deployment, so two schedulers can
          never assign the same deployment. The overview page shows node health and the last 24 hours of moves.
        </P>
      </Section>

      <Section id="sponsorships" title="Sponsorships and referrals">
        <P>
          Sponsored placements are optional and <strong>off by default</strong>. Under <strong>Sponsorships &amp; referrals</strong>, turn them on,
          choose which placements show items (landing page, docs, customer and provider dashboards, 1 to 3 items each) and manage campaigns for GPU
          clouds, inference and model-hosting platforms, cloud infrastructure, data centers and developer tools. A campaign is either a sponsored
          listing or resource (labelled &ldquo;Sponsored&rdquo;) or an outbound referral link (labelled &ldquo;Referral link&rdquo;), which can carry
          the partner&apos;s referral code and a campaign tag added to the link on click.
        </P>
        <P>
          Items link only to the campaign&apos;s stored https URL with <C>rel=&quot;sponsored&quot;</C>, are shown apart from organic content, and can
          be dismissed. Impressions count once per signed view token when at least half the item is visible; clicks count once per view. No personal
          data is used, no third-party ad scripts load, and campaigns never influence placement, health checks or security decisions. AgentMesh does
          not bill advertisers or track conversions: agreements and invoicing happen outside the platform.
        </P>
      </Section>

      <Section id="monitoring" title="Monitoring">
        <Table
          head={['Endpoint', 'Use']}
          rows={[
            [<C key="1">GET /health</C>, 'Liveness.'],
            [<C key="2">GET /health/ready</C>, 'Database (and Redis) readiness; 503 if either fails. Use for load balancers.'],
            [<C key="3">GET /metrics</C>, <>Prometheus, with <C>Authorization: Bearer $METRICS_TOKEN</C>.</>],
            [<C key="4">GET /api/v1/admin/overview</C>, 'Operator dashboard figures: nodes by health, overdue heartbeats, and failover activity (moves, ended attempts, deployments waiting for a node).'],
            [<C key="6">GET /api/v1/admin/anomalies</C>, 'Providers whose token claims exceed the request and response sizes the gateway observed, or whose requests mostly fail.'],
            [<C key="7">POST /api/v1/admin/nodes/&#123;id&#125;/quarantine</C>, 'Cut a node off at once (no authentication, tunnel closed, deployments moved); release with /release. See docs/security/INCIDENT_RESPONSE.md.'],
          ]}
        />
        <P>
          Logs are JSON lines with a request id; API keys, node credentials, bearer tokens and secret keys are redacted, and security events
          (session refusals, closed tunnels, rejected commands) are logged with an allowlist of fields under <C>agentmesh.security</C>. Alert on readiness
          failing, rising 5xx, many deployments in <C>PENDING</C> or <C>NEEDS_ATTENTION</C>, many nodes degraded or offline, and{' '}
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
            'After a restore: point MONGODB_DB at it, start the API, and check the overview (node health, deployments, recovery activity) before sending traffic to it.',
            'API restarts lose nothing: workers reconnect, pending placements resume, and cost estimates continue from each deployment’s watermark without counting anything twice.',
            <>Incident runbooks (compromised nodes, leaked credentials, key rotation, rollback) are in <A href={`${REPO_URL}/blob/main/docs/security/INCIDENT_RESPONSE.md`}>docs/security/INCIDENT_RESPONSE.md</A>.</>,
          ]}
        />
      </Section>

      <Section id="worker-releases" title="Publishing worker releases">
        <List
          ordered
          items={[
            <>Set <C>WORKER_VERSION</C> in <C>server/node_agent/config.py</C>, and <C>WORKER_VERSION</C> in <C>client/src/lib/config.ts</C> to match (a test checks this).</>,
            <>Commit, then tag and push: <C>git tag worker-v0.3.1 && git push origin worker-v0.3.1</C>.</>,
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
