import type { Metadata } from 'next';
import { C, Callout, Code, DocPage, List, P, Section, Table } from '@/components/docs/DocsContent';

export const metadata: Metadata = { title: 'AI deployment agent' };


export default function AiAgentGuide() {
  return (
    <DocPage href="/docs/ai-agent">
      <Callout tone="info" title="Availability">
        AI Deploy is available when the Gemini API is configured and answering. <C>/customer/ai</C> shows its live status. While
        Gemini cannot answer, requests wait in the queue and running deployments are not affected.
      </Callout>
      <Section id="how-it-works" title="How it works">
        <P>
          Customers describe a deployment in plain language (<C>/customer/ai</C>) and authorize limits. A language model turns the
          request into a structured plan and diagnoses failures, using Google&apos;s Gemini API. Everything with consequences runs in
          the control plane&apos;s own code: catalog checks, limits, prices, wallet balance, node selection, capacity reservation,
          submission, verification, and stopping.
        </P>
        <Table
          head={['Component', 'Runs on', 'Responsible for']}
          rows={[
            ['Control plane', 'The API (e.g. Render)', 'Auth, scheduling, reservations, billing, workflow state, audit, limit enforcement, and the calls to Gemini'],
            ['Gemini API', 'Google', 'Answers planning and recovery questions with JSON'],
            ['Compute nodes', 'Provider machines', 'Customer model deployments, through the existing worker'],
          ]}
        />
        <P>
          Every model call is queued first, so retries, expiry and cancellation do not depend on one HTTP call. The control plane
          answers each queued call right away with <C>models/GEMINI_MODEL:generateContent</C>; the API key travels in a header and
          never in a URL or log.
        </P>
        <Callout tone="info" title="What the model decides, and what it does not">
          The model chooses among catalog models and recovery actions and writes explanations. It never decides authorization, GPU
          availability, prices, budget compliance, or whether a deployment works. It cannot call submission, rollback, recovery or
          health-check tools itself; it can only propose them, and the application validates every proposal.
        </Callout>
      </Section>

      <Section id="gemini" title="Configure Gemini">
        <List
          ordered
          items={[
            <>Create an API key in Google AI Studio (<C>https://aistudio.google.com/apikey</C>).</>,
            <>Set it on the API as <C>GEMINI_API_KEY</C> (in the hosting platform&apos;s secret settings, never in the repository). Without it the agent is off and its endpoints answer <C>ai_not_configured</C>.</>,
            <>Optionally choose the model with <C>GEMINI_MODEL</C> (default <C>gemini-2.5-flash</C>). <C>GEMINI_THINKING_BUDGET=0</C> (default) turns off thinking tokens, which would otherwise use up <C>AI_MAX_TOKENS</C>; unset it for models that cannot turn thinking off, such as Pro models.</>,
            <>Check <C>GET /api/v1/ai/health</C>: <C>available</C> with a key, <C>not_configured</C> without one, and <C>degraded</C> for a few minutes after Gemini fails to answer.</>,
          ]}
        />
        <Table
          head={['Setting', 'Default', 'Meaning']}
          rows={[
            [<C key="1">GEMINI_TIMEOUT_SECONDS</C>, '60', 'Per call; must not exceed AI_REQUEST_TIMEOUT.'],
            [<C key="2">AI_MAX_ATTEMPTS</C>, '2', 'Deliveries per model call. Timeouts, 429 and 5xx answers are retried on the next background pass (about every 15 s); other errors fail the run without a decision.'],
            [<C key="3">AI_MAX_CONCURRENT_REQUESTS</C>, '1', 'Gemini calls in flight at once, across all runs.'],
          ]}
        />
        <Callout tone="warning" title="Customer requests go to Google">
          With Gemini, the customer&apos;s request text, the plan conversation and short tool results (catalog entries, deployment status
          and redacted log excerpts) are sent to Google for processing under the Gemini API terms. On Google&apos;s unpaid tier,
          Google may use that content to improve its products; use a paid (billing-enabled) project for production. Prompts sent to
          customers&apos; own deployments never go to Gemini.
        </Callout>
      </Section>

      <Section id="offline" title="When Gemini is unavailable">
        <List
          items={[
            'The control plane, database, billing, and every running customer deployment keep working. Deployment state lives in the database, not in the model conversation.',
            'A failed call (timeout, 429 or 5xx) is queued again and retried on the next background pass, up to AI_MAX_ATTEMPTS; the AI service shows as degraded meanwhile.',
            'New AI requests are accepted and queued (up to AI_QUEUE_MAX_LENGTH). A call not answered within AI_QUEUE_TTL_SECONDS fails with “No AI decision was made”; nothing is deployed.',
            'Deterministic steps continue: verification, duration and spend limits, stopping and cancellation all work without the model.',
          ]}
        />
      </Section>

      <Section id="limits" title="Autonomy limits">
        <P>Customers set these per request; they are enforced in code, never by the prompt:</P>
        <List
          items={[
            'Maximum spend: the plan’s estimate must fit, the wallet must cover it, and the deployment is stopped when rated charges plus unrated READY time reach it.',
            'Maximum duration: the deployment is stopped when it is reached.',
            'Maximum CPU cores, memory, and GPU memory (0 = no GPU).',
            'Maximum automatic recovery attempts (platform ceiling 3).',
            'Allowed runtimes (Ollama, llama.cpp, vLLM) and model sources (Ollama registry, Hugging Face).',
            'Agent steps and tool calls per run (platform settings).',
          ]}
        />
        <Callout tone="warning" title="Budget is checked, not held">
          The ledger has no holds, so “reserve budget” means: the wallet must cover the estimate when the deployment is created, node
          capacity is reserved atomically in the same transaction as the existing prepaid check, and spending is enforced by stopping
          the deployment. Another deployment could still use the same balance in the meantime.
        </Callout>
      </Section>

      <Section id="testing" title="Tests">
        <Code
          code={['cd server', 'pytest tests/test_ai_agent.py tests/test_ai_gemini.py     # against a fake Gemini API'].join('\n')}
        />
        <P>
          The tests never call Google, never create paid deployments (no price is configured unless a test sets one), and never use
          GPUs. The fake Gemini checks every request the way the real API requires (key in the header, alternating turns, JSON
          responses).
        </P>
      </Section>

      <Section id="not-verified" title="Not yet verified">
        <List
          items={[
            'The Gemini integration has been tested against a fake that mirrors the documented generateContent API, not against Google itself; the first real call happens once GEMINI_API_KEY is set.',
            'The quality of Gemini’s plans for this catalog has not been measured.',
            'The end-to-end flow was tested with scripted model answers and a simulated worker tunnel, not with a real provider node running a model.',
          ]}
        />
      </Section>
    </DocPage>
  );
}
