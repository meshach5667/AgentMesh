import type { Metadata } from 'next';
import { A, C, Callout, Code, DocPage, H3, List, P, Section, Table } from '@/components/docs/DocsContent';
import { ReleaseStatus } from '@/components/docs/ReleaseStatus';
import { API_URL, RELEASES_URL, WORKER_VERSION } from '@/lib/config';
import {
  WORKER_BIN,
  agentInstallCommand,
  dockerInstallCommand,
  serviceLogCommands,
  sourceInstallCommand,
  statusCommand,
  uninstallCommand,
  workerTag,
  workerWheel,
} from '@/lib/worker';
import { docMetadata } from '@/lib/seo';

export const metadata: Metadata = docMetadata('/docs/providers');

export default function ProviderGuide() {
  return (
    <DocPage href="/docs/providers">
      <Section id="how-it-works" title="How hosting works">
        <P>
          The AgentMesh worker runs open-weight models on your machine for customers&apos; deployments. It connects <strong>outbound</strong> to
          the control plane over HTTPS and a WebSocket, so you do not open any ports. You earn a share of what customers pay while your
          node serves their deployments.
        </P>
        <List
          items={[
            'It only uses the CPU, memory, disk and GPU you allocate. Defaults are half your CPU cores and RAM, at most 20 GB of disk, and no GPU.',
            'It never touches your own Ollama install: not port 11434, not ~/.ollama, not your models. Workloads get their own port, model directory and process.',
            'It never runs commands from customers. The control plane can only ask it to deploy an approved model with set limits, or to stop one.',
            'Every command is signed by the control plane and bound to your node, that command and its exact payload; the worker refuses anything unsigned, altered, expired or replayed. It pins the signing key when it enrolls.',
            'The worker signs a fresh challenge with a private key generated on your machine to get one-hour sessions, so a copied enrollment credential alone cannot impersonate your node. The key never leaves the machine (it is kept with 0600 permissions next to the credential).',
            'If an operator quarantines your node while investigating a problem, the worker keeps its credential and retries every minute; it resumes when released. If the node is revoked, it stops its workloads and deletes its credential.',
            'Hardware reports contain CPU model, cores, RAM, free disk, OS, architecture, and GPU model and VRAM. Nothing else is uploaded.',
          ]}
        />
        <Callout tone="warning" title="You can see customer data">
          As the machine owner you can inspect model files, process memory, and the prompts and responses your node handles. Customers are
          told this. Do not use your machine to inspect their data.
        </Callout>
      </Section>

      <Section id="prerequisites" title="Prerequisites">
        <Table
          head={['', 'Installable agent', 'Docker worker']}
          rows={[
            ['OS', 'Linux or macOS', 'Linux (Docker Engine 24+)'],
            ['Software', <>Python 3.11+ with <C>venv</C> (Debian/Ubuntu: <C>apt install python3-venv</C>), <A href="https://ollama.com/download">Ollama</A>, <C>curl</C></>, <>Docker Engine 24+ with Compose; NVIDIA Container Toolkit for GPUs; <C>git</C></>],
            ['Rights', 'No admin rights; installs for your user only', 'Access to the Docker socket (root-equivalent)'],
            ['Network', 'Outbound HTTPS to the control plane, GitHub and PyPI; Hugging Face/Ollama registry for models', 'Same'],
            ['Status', 'Verified on Linux; macOS not yet run on a real Mac', 'Not yet run against a real Docker daemon'],
          ]}
        />
      </Section>

      <Section id="enroll" title="Create an enrollment token">
        <List
          ordered
          items={[
            <>Sign up at <A href="/register?role=provider">provider registration</A> (or sign in).</>,
            <>Open <A href="/provider/nodes/register">Add a machine</A>, optionally name the machine and its region, and press <strong>Create token</strong>.</>,
            'The token works once and expires after 60 minutes. Create a new one for each machine. The page fills it into the install command for you.',
          ]}
        />
        <P>With the API, using your provider sign-in token:</P>
        <Code
          code={`curl -X POST ${API_URL}/nodes/enrollment-tokens \\
  -H "Authorization: Bearer $PROVIDER_JWT" -H "Content-Type: application/json" -d '{"name": "my-box"}'`}
        />
      </Section>

      <Section id="install-release" title="Install from a GitHub release">
        <ReleaseStatus />
        <P>
          Each worker release on <A href={RELEASES_URL}>GitHub Releases</A> is tagged <C>{workerTag()}</C> and contains{' '}
          <C>{workerWheel()}</C>, <C>install.sh</C>, <C>uninstall.sh</C> and <C>SHA256SUMS</C>. The command below downloads the release into{' '}
          <C>~/agentmesh-worker-{WORKER_VERSION}</C>, verifies every file against <C>SHA256SUMS</C> (stopping if any does not match), and only
          then runs the installer. Paste your token in place of <C>&lt;enrollment-token&gt;</C>; it is passed to the installer only, never put in
          a URL.
        </P>
        <Code title="Linux and macOS" code={agentInstallCommand()} />
        <P>The installer:</P>
        <List
          ordered
          items={[
            'checks your OS, Python and Ollama;',
            <>creates a private Python environment in <C>~/.local/share/agentmesh/venv-agentmesh-worker</C> and installs the wheel (its dependencies come from PyPI);</>,
            <>writes <C>~/.config/agentmesh/agentmesh-worker.env</C> with permissions 0600;</>,
            'enrolls the machine with the one-time token;',
            'starts a per-user background service: a systemd user unit on Linux, a launchd agent on macOS.',
          ]}
        />
        <H3>Useful options</H3>
        <Table
          head={['Option', 'Effect']}
          rows={[
            [<C key="1">--max-ram-mb / --max-cpu / --max-disk-mb</C>, 'The most AgentMesh will ever reserve on this machine.'],
            [<C key="2">--schedule &quot;mon-fri 18:00-08:00&quot;</C>, 'Only take work in these local-time windows. Also “weekends 00:00-24:00”, “daily 22:00-07:00”.'],
            [<C key="3">--outside-schedule pause|drain</C>, 'Outside the schedule, keep running deployments (pause, default) or move them away (drain).'],
            [<C key="4">--linger</C>, 'Linux: keep the worker running while you are logged out.'],
            [<C key="5">--no-service</C>, <>Do not install a service; run <C>agentmesh-worker run</C> under your own supervisor.</>],
            [<C key="6">--update-public-key KEY</C>, 'Pin the operator’s release-signing key so signed self-updates are accepted.'],
            [<><C>--token</C> omitted</>, 'The installer prompts for the token without echoing it.'],
          ]}
        />
        <Callout title="What the checksum protects against">
          <C>SHA256SUMS</C> comes from the same release, so it catches corrupted or partial downloads, not a compromised GitHub account. Signed
          self-updates (below) use an offline key that GitHub never sees.
        </Callout>
        <P>
          On Linux, each model runs in its own systemd scope with hard memory and CPU limits. On macOS the limits are advisory: the scheduler
          never reserves more than you allow, but the OS does not enforce it.
        </P>
      </Section>

      <Section id="install-source" title="Install from source">
        <P>Use this before the first release is published, or to run unreleased code. It builds the same wheel locally.</P>
        <Code code={sourceInstallCommand()} />
      </Section>

      <Section id="docker" title="Docker worker">
        <P>
          The Docker worker runs each deployment in its own container. It needs the Compose file from the repository, so it uses a checkout
          rather than the release downloads.
        </P>
        <Code code={dockerInstallCommand()} />
        <Callout tone="danger" title="Docker socket access is root-equivalent">
          The worker needs the Docker socket to create workload containers, which is equivalent to root on the host. Prefer rootless Docker
          and a machine dedicated to this purpose. Workload containers never get the socket.
        </Callout>
        <P>Each workload container runs with:</P>
        <List
          items={[
            'memory and swap limits, a CPU quota and a PID limit;',
            'all Linux capabilities dropped, no-new-privileges, and a read-only root filesystem;',
            'no host bind mounts, only the agentmesh-models volume;',
            'a private network with no internet access once the model is downloaded;',
            <>a GPU only if the deployment needs one and you set <C>AGENTMESH_ALLOW_GPU=true</C>.</>,
          ]}
        />
        <P>
          Known gaps: the Docker worker has not yet been run against a real Docker daemon, and it does not detect GPUs inside its container,
          so it currently advertises no GPU. View logs with <C>docker compose -f docker-compose.worker.yml logs -f worker</C>.
        </P>
      </Section>

      <Section id="status-checks" title="Check the worker">
        <P>
          The machine appears under <A href="/provider/nodes">My Nodes</A> a few seconds after it enrolls. On the machine
          (installable agent), the worker command lives in its private environment:
        </P>
        <Code code={statusCommand} />
        <Table
          head={['Platform', 'Service status and logs']}
          rows={[
            ['Linux', <pre key="l" className="whitespace-pre-wrap font-mono text-xs">{serviceLogCommands.linux}</pre>],
            ['macOS', <pre key="m" className="whitespace-pre-wrap font-mono text-xs">{serviceLogCommands.macos}</pre>],
          ]}
        />
        <P>
          <C>doctor</C> checks the platform, Python, config, control plane, credential, Ollama, resource limits, disk, memory, GPUs and schedule,
          and prints a fix for each problem. <C>doctor --deep</C> also starts a throwaway Ollama instance.
        </P>
      </Section>

      <Section id="manage" title="Manage machines">
        <Table
          head={['Action', 'Where', 'Effect']}
          rows={[
            ['Pause new work', 'Dashboard, or worker pause', 'No new placements; running deployments keep serving.'],
            ['Drain', <C key="d">{`${WORKER_BIN.split('/').pop()} drain`}</C>, 'Stop taking work and stop running deployments; AgentMesh moves them to other nodes when possible.'],
            ['Resume', 'Dashboard, or worker resume', 'Take work again (within your schedule). Dashboard and local pause are independent; both must be off.'],
            ['Revoke', 'Dashboard', 'Disables the node’s credential at once; deployments move elsewhere when possible.'],
          ]}
        />
        <P>
          A node is shown as <strong>Accepting work</strong>, <strong>Paused</strong>, <strong>Unavailable</strong> (paused, draining or outside its
          schedule on the machine), <strong>Offline</strong> (no heartbeats) or <strong>Revoked</strong>. The node page shows each runtime the worker
          reported, whether its limits are enforced or advisory, how much of your allocation is reserved, and the last reported load.
        </P>
      </Section>

      <Section id="community-models" title="Community models (opt-in)">
        <P>
          Customers can import public GGUF models from Hugging Face for their own deployments. No operator reviews these, so AgentMesh only
          places them on nodes whose provider turns on <strong>Accept community models</strong> on the node page. It is off by default, and
          operators cannot turn it on for you.
        </P>
        <List
          items={[
            'They run only with llama.cpp. The worker downloads one GGUF file from Hugging Face at a pinned commit and refuses it unless its SHA-256 matches.',
            'Gated, private and non-commercially licensed models, and code-carrying formats such as pickles, are refused before they reach you.',
            'What the model generates is not reviewed.',
            'Turning it off stops new placements. Community deployments already running keep running until they stop or move.',
          ]}
        />
      </Section>

      <Section id="pricing" title="Set your prices">
        <List
          items={[
            'Each machine has its own price list: per CPU core-hour, per GB-hour of memory and of GPU memory, and per million input and output tokens. Set it on the machine\'s page under Pricing; the form shows what you keep after the platform commission.',
            'Under Settings, set default prices that every machine you enroll starts with, and optionally publish them on all your active machines at once.',
            'A machine without its own prices charges the network prices set by the operator.',
            'Customers are placed on the cheapest machine that fits. Unless a customer raises their price limit, they are only placed on machines at or below the network prices, so pricing above them means fewer placements.',
            'New prices apply at once to new placements. Deployments already on your machine never pay more than the prices they were placed at: a cut reaches them immediately, a rise only applies to deployments placed after it.',
            'Every price change is kept as a version with its time, and each charge records the prices it was rated at.',
          ]}
        />
      </Section>

      <Section id="earnings" title="Earnings and payouts">
        <Callout tone="warning" title="Paystack test mode">Payouts run through Paystack in test mode. No real money is transferred yet.</Callout>
        <List
          items={[
            'You are credited your share of each charge for deployments your nodes served: everything except the platform commission (10% unless the operator set another rate; the wallet page shows the rate in force). Earnings & Payouts shows each charge with what the customer paid, the commission and your share, plus totals for the last 30 days.',
            'Add a bank account there. Paystack verifies it, and only its last four digits are stored. Then request a payout.',
            'The amount is held from your balance at once. An operator approves the payout and Paystack transfers it. A failed or rejected payout returns the money.',
            'Served Usage shows the requests your nodes answered.',
            'If an operator refunds a charge your node earned, your share of the refunded amount is reversed (a Refund clawback entry). If you were already paid out, your balance can go negative until later earnings cover it.',
            'Earnings over time charts your share and the commission per day; Transactions can be filtered and exported as CSV.',
          ]}
        />
      </Section>

      <Section id="troubleshooting" title="Troubleshooting">
        <P>Start with <C>agentmesh-worker doctor</C> (see <A href="#status-checks">Check the worker</A>).</P>
        <Table
          head={['Problem', 'What to do']}
          rows={[
            ['python3 venv module missing', <><C key="a">sudo apt install python3-venv</C> (Debian/Ubuntu), then rerun the installer.</>],
            ['Ollama not found', <>Install it from <A href="https://ollama.com/download">ollama.com/download</A>, or pass <C>--ollama /path/to/ollama</C>.</>],
            ['…agentmesh-worker.env already exists', <>A worker with that name is installed. Run <C>./uninstall.sh</C> first, or use <C>--name</C> for a second worker.</>],
            ['sha256sum: … FAILED', 'A download is corrupt or incomplete. Delete the folder and download again; do not run install.sh.'],
            ['Enrollment fails', 'Tokens work once and expire after 60 minutes. Create a new token in the dashboard.'],
            ['Node shows Offline', <>Check the service status and logs above, and that the machine can reach <C>{API_URL.replace('/api/v1', '')}</C>.</>],
          ]}
        />
        <Table
          head={['Deployment error', 'Meaning']}
          rows={[
            [<C key="1">INSUFFICIENT_DISK / INSUFFICIENT_MEMORY</C>, 'The machine does not currently have the reserved resources free. Lower your allocation if it happens often.'],
            [<C key="2">MODEL_PULL_FAILED / MODEL_PULL_STALLED</C>, 'Download failed. Transient errors are retried 3 times first.'],
            [<C key="3">MODEL_INTEGRITY_FAILED</C>, 'The downloaded file did not match the catalog’s SHA-256 or size; it was deleted.'],
            [<C key="4">HEALTHCHECK_FAILED</C>, <>The model could not answer a test prompt. Check the log in the data directory&apos;s <C>logs/</C>.</>],
            [<C key="5">RUNTIME_START_FAILED</C>, 'Ollama (or the container) did not start.'],
            [<C key="6">NODE_UNAVAILABLE</C>, 'You paused or drained the machine, or its schedule ended. The deployment moves elsewhere if possible.'],
          ]}
        />
      </Section>

      <Section id="uninstall" title="Uninstall">
        <Code title="Installable agent" code={uninstallCommand()} />
        <P>
          This stops the service and every managed workload, and deletes the credential, config, private environment and (with{' '}
          <C>--purge-models</C>) downloaded models. Your own Ollama is left untouched. For the Docker worker run{' '}
          <C>docker compose -f docker-compose.worker.yml down -v</C>. Then revoke the node in the dashboard.
        </P>
      </Section>

      <Section id="releases" title="How worker releases are made">
        <P>
          Releases are built by GitHub Actions when a maintainer pushes a tag <C>worker-v&lt;version&gt;</C> matching <C>WORKER_VERSION</C> in{' '}
          <C>server/node_agent/config.py</C>. The workflow builds the wheel reproducibly, checks it installs, writes <C>SHA256SUMS</C>, and attaches
          the assets to the release. See <A href="/docs/operators#worker-releases">Publishing worker releases</A>.
        </P>
        <P>
          Signed self-updates are separate: operators sign release manifests with an offline Ed25519 key, and workers installed with{' '}
          <C>--update-public-key</C> accept only releases signed by it, so even a compromised control plane cannot push code to your machine.
          That key is never stored in GitHub Actions.
        </P>
      </Section>
    </DocPage>
  );
}
