import type { Metadata } from 'next';
import { TrustNotice } from '@/components/common/Notices';
import { A, C, Callout, Code, DocPage, List, P, Section, Table } from '@/components/docs/DocsContent';
import { API_URL } from '@/lib/config';
import { docMetadata } from '@/lib/seo';

export const metadata: Metadata = docMetadata('/docs/customers');

export default function CustomerGuide() {
  return (
    <DocPage href="/docs/customers">
      <Callout tone="info">
        Everything here is done in the <A href="/customer">customer dashboard</A>. The same actions are available
        through the API; see the <A href="/docs/api">API reference</A>.
      </Callout>

      <Section id="models" title="Browse models">
        <P>
          Under <strong>Models</strong>, each card shows the runtimes that can serve the model (green means a node offering that runtime is
          online now), the smallest memory reservation, and when a deployment of it last passed its readiness test. Only models an
          operator has approved are listed. Being in the catalog does not guarantee a node with enough free capacity is online.
        </P>
        <Table
          head={['Runtime', 'Serves', 'Hardware', 'Notes']}
          rows={[
            [<C key="o">ollama</C>, 'Ollama registry tags', 'CPU or GPU', 'Widest node availability. Also exposes Ollama’s own API.'],
            [<C key="l">llamacpp</C>, 'One GGUF file from Hugging Face, pinned to a commit and checked by SHA-256', 'CPU', 'Smaller reservations for the same model.'],
            [<C key="v">vllm</C>, 'A full Hugging Face repository at a pinned commit', 'GPU required', 'Not yet verified on real GPU hardware.'],
          ]}
        />
        <P>Gated or private Hugging Face models are not supported: AgentMesh never sends access tokens to provider machines.</P>
      </Section>

      <Section id="huggingface" title="Import a model from Hugging Face">
        <P>
          Under <strong>Models</strong>, <strong>Your models from Hugging Face</strong> imports a public GGUF file for your own use. Enter a
          repository (<C>owner/name</C>) or a huggingface.co link, press <strong>Look up</strong>, choose a file, confirm you may use it under
          its license, and import. It then deploys like any other model.
        </P>
        <List
          items={[
            'Private to you: other customers cannot see or deploy it, and the AI deployment assistant does not use it.',
            'Pinned: AgentMesh records the commit you looked up and the file’s SHA-256 from Hugging Face. Providers verify the hash before loading, so later changes to the repository never reach your deployment. Import again to pick up a newer commit.',
            'Served by llama.cpp only, on nodes whose providers accept community models. Fewer nodes may have room for it.',
            'Memory and disk reservations are estimated from the file size.',
          ]}
        />
        <Table
          head={['Refused', 'Why']}
          rows={[
            ['Gated, private or disabled repositories', 'AgentMesh never sends Hugging Face tokens to provider machines.'],
            ['No declared license, or a non-commercial one (e.g. cc-by-nc-4.0)', 'Hosting on AgentMesh is paid, so it is commercial use.'],
            ['Formats other than single-file GGUF (safetensors repos, .bin/.pt pickles, split GGUFs, mmproj files)', 'Only a single GGUF file can be hash-pinned, and pickles can run code when loaded.'],
            ['Files over the size limit (16 GB by default)', 'Keeps downloads on provider machines reasonable.'],
          ]}
        />
        <P>
          You are responsible for using the model within its license. Operators can disable an imported model, or approve it into the public
          catalog. To remove one, stop its deployments, then press <strong>Remove</strong>.
        </P>
      </Section>

      <Section id="providers" title="Choose a provider">
        <P>
          <strong>Compute providers</strong> lists the independent providers with machines taking work right now: how many machines, GPUs,
          runtimes, their lowest prices per currency, and how they take payment. Open a provider to see their full payment arrangement, and
          use <strong>Deploy on …</strong> to run only on their machines. Or let AgentMesh pick the cheapest suitable machine from any
          provider. Listings never depend on sponsorships.
        </P>
      </Section>

      <Section id="deploy" title="Deploy a model">
        <List
          ordered
          items={[
            'Open a model and choose a runtime, or Automatic (tries Ollama, then llama.cpp, then vLLM, and uses the first that fits on a node).',
            'Set the context window (512 to 8192 tokens) and, optionally, a region or a GPU requirement. The form shows what the scheduler will reserve and the price of the cheapest machine that can take it.',
            'Optionally choose a provider, set price limits (the most per hour while ready, and per million tokens, in a currency), and choose what happens if the node fails.',
            'Read and confirm the trust notice, then press Deploy.',
          ]}
        />
        <P>
          If no node can take it, the form explains why for each runtime, for example &ldquo;runtime not installed on the node&rdquo; or
          &ldquo;not enough free CPU, memory, disk or GPU memory&rdquo;, or &ldquo;charges more than your price limit&rdquo;. No balance or
          prepayment is needed: you pay the provider directly (see <A href="#payment">payment</A>).
        </P>
      </Section>

      <Section id="lifecycle" title="Monitor a deployment">
        <P>The deployment page updates every 2 seconds while it starts, and shows each event, the verified model digest, and any error.</P>
        <Table
          head={['Status', 'Meaning']}
          rows={[
            [<C key="1">SCHEDULED</C>, 'Assigned: capacity reserved on a node.'],
            [<C key="2">PROVISIONING</C>, 'Runtime starting and model downloading.'],
            [<C key="3">STARTING</C>, 'Model loading; a test generation is run.'],
            [<C key="4">READY</C>, 'The test generation succeeded. The endpoint is live.'],
            [<C key="5">UNHEALTHY</C>, 'The node stopped reporting or the health check fails; requests get 503. If it does not recover within 3 minutes, the deployment moves to another node.'],
            [<><C>STOPPING</C> → <C>STOPPED</C> / <C>CANCELLED</C></>, 'Stopped after (or before) it was ready.'],
            [<C key="8">PENDING</C>, 'Waiting for a node: its node failed and no eligible replacement is free yet. Retried automatically with growing intervals for up to an hour.'],
            [<C key="9">NEEDS_ATTENTION</C>, 'Waiting for you: your failover policy is manual, or only machines that cost more than its previous placement are available.'],
            [<C key="7">FAILED</C>, 'See the error code and message on the page.'],
          ]}
        />
        <P>
          <strong>Restart</strong> reloads a serving deployment on its current node from the cached model.
        </P>
      </Section>

      <Section id="failover" title="When a node fails">
        <List
          items={[
            'Every machine sends a heartbeat about every 15 seconds. One late heartbeat stops new work going to it; after 90 seconds of silence it is marked offline.',
            'A deployment still starting on a failed node moves at once; a serving one becomes UNHEALTHY and moves if the node does not recover within 3 minutes.',
            'The replacement is the cheapest healthy machine with the same requirements (runtime, memory, GPU, region), within your price limits and provider choice, and never a machine that already failed this deployment.',
            'Without price limits of your own, a move never costs more than the placement it replaces; if only dearer machines are free, the deployment waits for you (NEEDS_ATTENTION) until you raise the limit and retry.',
            'With no suitable machine free it waits (PENDING) and is retried automatically; after an hour, or after 5 placements in total, it fails with a clear reason.',
            'A move restarts the model on the new machine from its pinned source and verifies it again. It is not a live migration: requests in flight on the failed node are lost and can be retried. The id, endpoint and API keys stay the same.',
            'Failures caused by the model itself, such as a model that cannot answer a test prompt, are not retried elsewhere because another node would fail the same way.',
            'Failover policy: "any provider" (default), "same provider only", or "ask me first" (never moved automatically). Change it, and your price limits, on the deployment page.',
            'Planned moves: when a provider takes a machine out of service (Move work off, or draining the worker), your deployment is moved without interruption. The replacement starts first, traffic switches the moment it is ready, and the old copy keeps serving in-flight requests for two more minutes before it stops. If the replacement fails, nothing changes.',
            'The deployment page lists every attempt: which provider ran it, when it served, and why it ended.',
          ]}
        />
      </Section>

      <Section id="api-keys" title="API keys">
        <P>
          Create keys under <strong>API Keys</strong>. A key can be limited to one deployment and given an expiry date. The key (
          <C>am_sk_…</C>) is shown once; AgentMesh stores only a hash. Revoke a key at any time. Deleting a deployment revokes the keys
          scoped to it. API keys work for calling deployments only; account actions (deploying, billing) use your dashboard sign-in.
        </P>
      </Section>

      <Section id="call" title="Call your model">
        <P>
          A ready deployment has <strong>Try it</strong>, which sends one real request through the gateway (metered like any other), and
          copy-paste examples. Every deployment has an OpenAI-compatible base URL:
        </P>
        <Code
          title="curl"
          code={`curl ${API_URL}/deployments/<deployment-id>/v1/chat/completions \\
  -H "Authorization: Bearer $AGENTMESH_API_KEY" -H "Content-Type: application/json" \\
  -d '{"model": "qwen2.5:0.5b", "messages": [{"role": "user", "content": "Hello"}]}'`}
        />
        <Code
          title="Python (openai)"
          code={`import os
from openai import OpenAI

client = OpenAI(
    base_url="${API_URL}/deployments/<deployment-id>/v1",
    api_key=os.environ["AGENTMESH_API_KEY"],
)
reply = client.chat.completions.create(
    model="qwen2.5:0.5b",
    messages=[{"role": "user", "content": "Hello"}],
)
print(reply.choices[0].message.content)`}
        />
        <P>
          More, including streaming and Ollama&apos;s native API, is in the <A href="/docs/api#inference">API reference</A>.
        </P>
      </Section>

      <Section id="stop" title="Stop and delete">
        <P>
          <strong>Stop</strong> ends a deployment and releases its capacity. <strong>Delete</strong> also hides it and revokes keys scoped to
          it; usage records are kept. Cost estimates stop when a deployment leaves READY.
        </P>
      </Section>

      <Section id="payment" title="Prices, payment and cost estimates">
        <List
          items={[
            'Each machine has its own prices, set by its provider in their own currency: per CPU core-hour, per GB-hour of memory and of GPU memory, and per million input and output tokens. A machine without prices is free.',
            'Your deployment goes to the cheapest machine that fits within your price limits. Machines priced in a different currency from your limits are used only if they are free.',
            'You are never estimated above the prices in force when your deployment was placed on its machine. If the provider lowers them, the lower price applies; a rise only applies to new placements.',
            <>To use a provider&apos;s priced machines you first buy <strong>prepaid credit</strong> with that provider, under <strong>Prepaid credit</strong>. You pay the provider <strong>directly</strong>: through their own Paystack, Flutterwave or Stripe account (AgentMesh verifies the payment with their gateway the moment you return from checkout), or by transfer, which is credited when the provider confirms receiving it. The money never passes through AgentMesh, which takes no commission.</>,
            'Placement uses a priced machine only if your verified credit with its provider covers an hour of the reservation. Usage draws the credit down at the machine’s prices; when it is used up, requests are refused (402) and the deployment pauses (NEEDS_ATTENTION). It restarts automatically once a new payment is verified. Credit can dip below zero by at most one estimate window (about 5 minutes of use).',
            'Refunds of unused credit are between you and the provider; AgentMesh does not hold money to refund.',
            <><strong>Estimated costs</strong> shows what your deployments come to: reserved resources multiplied by READY time, plus tokens, per currency. Downloads, startup and unhealthy time are not counted, nor are failed requests. These are estimates, not bills or payments.</>,

            'Dashboards may show items labelled “Sponsored” or “Referral link” if the operator enabled them. They are chosen without your personal data, never affect where your deployment runs, and you can dismiss them.',
          ]}
        />
      </Section>

      <Section id="usage" title="Usage">
        <P>
          <strong>Usage</strong> shows requests, failures, and input and output tokens per day and per deployment. Token counts are reported by the
          model runtime on the provider&apos;s machine and are not independently verified. Requests whose runtime reported no counts are shown
          separately; AgentMesh never estimates token counts. Prompts and responses are not stored.
        </P>
      </Section>

      <Section id="privacy" title="Privacy">
        <TrustNotice />
        <P>
          The dashboard shows this notice before every deployment and asks you to confirm it. Read more in{' '}
          <A href="/docs/security#trust-model">Security &amp; limitations</A>.
        </P>
      </Section>
    </DocPage>
  );
}
