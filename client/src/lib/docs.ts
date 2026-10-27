export interface DocSection {
  id: string;
  title: string;
  keywords?: string;
}

export interface DocPageEntry {
  href: string;
  title: string;
  summary: string;
  sections: DocSection[];
}

export const DOC_PAGES: DocPageEntry[] = [
  {
    href: '/docs/getting-started',
    title: 'Getting started',
    summary: 'What AgentMesh is, who it is for, accounts and roles, and the live links.',
    sections: [
      { id: 'what-it-is', title: 'What AgentMesh does', keywords: 'overview open-weight models community compute' },
      { id: 'who-its-for', title: 'Who it is for', keywords: 'customers providers operators' },
      { id: 'accounts', title: 'Accounts and roles', keywords: 'sign up register login customer provider operator admin' },
      { id: 'status', title: 'What works today', keywords: 'status verified limitations planned' },
      { id: 'links', title: 'Live links', keywords: 'dashboard api url github releases repository' },
    ],
  },
  {
    href: '/docs/customers',
    title: 'Customer guide',
    summary: 'Deploy a model, call it with an API key, and understand billing.',
    sections: [
      { id: 'models', title: 'Browse models', keywords: 'catalog runtimes ollama llama.cpp vllm' },
      { id: 'huggingface', title: 'Import a model from Hugging Face', keywords: 'huggingface hf gguf community import custom own model license' },
      { id: 'deploy', title: 'Deploy a model', keywords: 'deployment context window region gpu' },
      { id: 'lifecycle', title: 'Monitor a deployment', keywords: 'status ready scheduled provisioning unhealthy failover' },
      { id: 'api-keys', title: 'API keys', keywords: 'create revoke scope expiry' },
      { id: 'call', title: 'Call your model', keywords: 'openai curl python playground' },
      { id: 'stop', title: 'Stop and delete', keywords: 'stop delete revoke keys' },
      { id: 'billing', title: 'Pricing, wallet and billing', keywords: 'paystack top-up charges prepaid balance insufficient funds refund csv export sponsored' },
      { id: 'usage', title: 'Usage', keywords: 'tokens requests metering' },
      { id: 'privacy', title: 'Privacy', keywords: 'provider can see prompts responses trust' },
    ],
  },
  {
    href: '/docs/providers',
    title: 'Provider guide',
    summary: 'Install the worker, enroll machines, manage them, and get paid.',
    sections: [
      { id: 'how-it-works', title: 'How hosting works', keywords: 'outbound connections ports resources' },
      { id: 'prerequisites', title: 'Prerequisites', keywords: 'python 3.11 venv ollama linux macos' },
      { id: 'enroll', title: 'Create an enrollment token', keywords: 'one-time token 60 minutes' },
      { id: 'install-release', title: 'Install from a GitHub release', keywords: 'prebuilt wheel install.sh sha256sums checksum download' },
      { id: 'install-source', title: 'Install from source', keywords: 'clone build wheel' },
      { id: 'docker', title: 'Docker worker', keywords: 'docker compose socket root rootless' },
      { id: 'status-checks', title: 'Check the worker', keywords: 'status doctor systemctl launchctl logs' },
      { id: 'manage', title: 'Manage machines', keywords: 'pause drain resume revoke schedule' },
      { id: 'community-models', title: 'Community models (opt-in)', keywords: 'huggingface gguf unreviewed opt in consent' },
      { id: 'earnings', title: 'Earnings and payouts', keywords: 'bank account paystack payout clawback refund' },
      { id: 'troubleshooting', title: 'Troubleshooting', keywords: 'errors insufficient memory pull failed healthcheck' },
      { id: 'uninstall', title: 'Uninstall', keywords: 'remove purge models revoke' },
      { id: 'releases', title: 'How worker releases are made', keywords: 'github actions tag worker-v release signed update' },
    ],
  },
  {
    href: '/docs/api',
    title: 'API reference',
    summary: 'Authentication, models, deployments, inference, streaming, keys, errors and usage.',
    sections: [
      { id: 'base-url', title: 'Base URL', keywords: 'endpoint https' },
      { id: 'auth', title: 'Authentication', keywords: 'jwt login register bearer token api key' },
      { id: 'models', title: 'Models', keywords: 'catalog artifacts runtimes' },
      { id: 'deployments', title: 'Deployments', keywords: 'create poll events stop restart delete idempotency' },
      { id: 'api-keys', title: 'API keys', keywords: 'create list revoke' },
      { id: 'inference', title: 'Inference', keywords: 'chat completions openai ollama' },
      { id: 'streaming', title: 'Streaming', keywords: 'stream sse ndjson include_usage' },
      { id: 'sdks', title: 'SDK examples', keywords: 'python openai javascript node' },
      { id: 'errors', title: 'Errors and limits', keywords: 'error codes rate limit 429 503 409 402' },
      { id: 'usage', title: 'Usage and billing', keywords: 'usage summary charges pricing' },
    ],
  },
  {
    href: '/docs/operators',
    title: 'Operators & self-hosting',
    summary: 'Run your own AgentMesh: configuration, deployment, catalog, pricing, payments and recovery.',
    sections: [
      { id: 'hosted-vs-self', title: 'Hosted vs. your own instance', keywords: 'self-host' },
      { id: 'configuration', title: 'Configuration', keywords: 'environment variables secret key cors mongodb url' },
      { id: 'deploy', title: 'Deploy', keywords: 'docker compose vercel render tls proxy' },
      { id: 'database', title: 'Database', keywords: 'mongodb atlas replica set indexes postgres migration' },
      { id: 'first-operator', title: 'First operator', keywords: 'create_operator admin' },
      { id: 'catalog', title: 'Model catalog', keywords: 'approve artifacts' },
      { id: 'pricing', title: 'Pricing', keywords: 'price list version commission platform fee 10% provider share' },
      { id: 'paystack', title: 'Payments (Paystack)', keywords: 'webhook test mode live key payouts otp' },
      { id: 'revenue', title: 'Revenue analytics', keywords: 'revenue commission analytics chart platform revenue' },
      { id: 'refunds', title: 'Refunds', keywords: 'refund clawback reversal card wallet paystack' },
      { id: 'sponsorships', title: 'Sponsorships', keywords: 'sponsored ads advertising campaign placement cpm cpc impressions clicks' },
      { id: 'monitoring', title: 'Monitoring', keywords: 'health ready metrics prometheus alerts' },
      { id: 'backups', title: 'Backups and recovery', keywords: 'mongodump restore runbook reconciliation' },
      { id: 'worker-releases', title: 'Publishing worker releases', keywords: 'release tag signed updates' },
    ],
  },
  {
    href: '/docs/ai-agent',
    title: 'AI deployment agent',
    summary: 'Gemini API (default) or Gemma 4 on an internal Ollama machine: setup, limits, offline behaviour and tests.',
    sections: [
      { id: 'how-it-works', title: 'How it works', keywords: 'gemini gemma ollama agent architecture outbound adapter' },
      { id: 'gemini', title: 'Use the Gemini API (default)', keywords: 'gemini api key google ai studio gemini-2.5-flash provider' },
      { id: 'hardware', title: 'Alternative: check the inference machine', keywords: 'cpu ram disk gpu doctor hp 15 laptop' },
      { id: 'model', title: 'Choose a Gemma 4 variant', keywords: 'gemma4 e2b e4b qat model tag size' },
      { id: 'install', title: 'Install Ollama and the model', keywords: 'pull check drop-in systemd' },
      { id: 'connect', title: 'Connect it to AgentMesh', keywords: 'ai_inference_token environment variables adapter' },
      { id: 'systemd', title: 'Run it at startup', keywords: 'systemd user service linger journalctl' },
      { id: 'monitoring', title: 'Monitor CPU and memory', keywords: 'load memory overload health' },
      { id: 'offline', title: 'Restarts and disconnections', keywords: 'offline queue expire reconnect resume' },
      { id: 'limits', title: 'Autonomy limits', keywords: 'budget spend duration recovery runtime source' },
      { id: 'testing', title: 'Tests', keywords: 'pytest integration real ollama' },
      { id: 'not-verified', title: 'Not yet verified', keywords: 'limitations unmeasured' },
    ],
  },
  {
    href: '/docs/security',
    title: 'Security & limitations',
    summary: 'Trust model, data visibility, controls, residual risks and what is not verified.',
    sections: [
      { id: 'trust-model', title: 'Trust model', keywords: 'provider sees prompts confidential' },
      { id: 'data', title: 'What data is stored', keywords: 'usage logs prompts not stored argon2 sessions' },
      { id: 'retention', title: 'Retention and deletion', keywords: 'retention delete days backups ai runs audit' },
      { id: 'worker-safety', title: 'Worker safety for providers', keywords: 'isolation ollama limits commands' },
      { id: 'controls', title: 'Platform controls', keywords: 'rate limit headers redaction webhooks mfa totp sessions refresh quarantine csp signed commands' },
      { id: 'risks', title: 'Known risks', keywords: 'residual risks localStorage mfa' },
      { id: 'not-verified', title: 'Not yet verified', keywords: 'paystack live gpu vllm docker macos' },
      { id: 'reporting', title: 'Reporting a vulnerability', keywords: 'security disclosure' },
    ],
  },
];

export interface SearchHit {
  href: string;
  title: string;
  page: string;
}

export function searchDocs(query: string, limit = 8): SearchHit[] {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!terms.length) return [];
  const hits: (SearchHit & { score: number })[] = [];
  for (const page of DOC_PAGES) {
    const entries = [
      { href: page.href, title: page.title, text: `${page.title} ${page.summary}`, boost: 1 },
      ...page.sections.map((s) => ({ href: `${page.href}#${s.id}`, title: s.title, text: `${s.title} ${s.keywords ?? ''}`, boost: 0 })),
    ];
    for (const e of entries) {
      const text = e.text.toLowerCase();
      if (!terms.every((t) => text.includes(t))) continue;
      const score = terms.reduce((n, t) => n + (e.title.toLowerCase().includes(t) ? 2 : 1), e.boost);
      hits.push({ href: e.href, title: e.title, page: page.title, score });
    }
  }
  return hits.sort((a, b) => b.score - a.score).slice(0, limit).map(({ href, title, page }) => ({ href, title, page }));
}
