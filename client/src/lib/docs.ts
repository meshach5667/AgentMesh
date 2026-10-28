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
    summary: 'Choose a provider, deploy a model, call it, understand failover, and pay providers directly.',
    sections: [
      { id: 'providers', title: 'Choose a provider', keywords: 'discover compute providers offers prices payment terms' },
      { id: 'models', title: 'Browse models', keywords: 'catalog runtimes ollama llama.cpp vllm' },
      { id: 'huggingface', title: 'Import a model from Hugging Face', keywords: 'huggingface hf gguf community import custom own model license' },
      { id: 'deploy', title: 'Deploy a model', keywords: 'deployment context window region gpu' },
      { id: 'lifecycle', title: 'Monitor a deployment', keywords: 'status ready scheduled provisioning unhealthy pending needs attention' },
      { id: 'failover', title: 'When a node fails', keywords: 'failover reroute heartbeat replacement attempts retry policy manual migration' },
      { id: 'api-keys', title: 'API keys', keywords: 'create revoke scope expiry' },
      { id: 'call', title: 'Call your model', keywords: 'openai curl python playground' },
      { id: 'stop', title: 'Stop and delete', keywords: 'stop delete revoke keys' },
      { id: 'payment', title: 'Prices, payment and cost estimates', keywords: 'provider prices price limit cheapest currency pay directly payment reference estimate no commission sponsored referral' },
      { id: 'usage', title: 'Usage', keywords: 'tokens requests metering' },
      { id: 'privacy', title: 'Privacy', keywords: 'provider can see prompts responses trust' },
    ],
  },
  {
    href: '/docs/providers',
    title: 'Provider guide',
    summary: 'Install the worker, enroll machines, set their prices, keep them healthy, and get paid directly.',
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
      { id: 'health', title: 'Health and failover', keywords: 'heartbeat degraded offline recovering benched failover' },
      { id: 'pricing', title: 'Set your prices', keywords: 'price list machine per hour tokens default currency free' },
      { id: 'payment', title: 'Get paid directly', keywords: 'payment arrangement bank transfer link terms estimates customer reference no commission' },
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
      { id: 'deployments', title: 'Deployments', keywords: 'create poll events stop restart delete idempotency retry attempts failover price limits provider' },
      { id: 'api-keys', title: 'API keys', keywords: 'create list revoke' },
      { id: 'inference', title: 'Inference', keywords: 'chat completions openai ollama' },
      { id: 'streaming', title: 'Streaming', keywords: 'stream sse ndjson include_usage' },
      { id: 'sdks', title: 'SDK examples', keywords: 'python openai javascript node' },
      { id: 'errors', title: 'Errors and limits', keywords: 'error codes rate limit 429 503 409' },
      { id: 'usage', title: 'Usage, providers and cost estimates', keywords: 'usage summary providers offers estimates market pricing' },
    ],
  },
  {
    href: '/docs/operators',
    title: 'Operators & self-hosting',
    summary: 'Run your own AgentMesh: configuration, deployment, catalog, failover tuning, sponsorships and recovery.',
    sections: [
      { id: 'hosted-vs-self', title: 'Hosted vs. your own instance', keywords: 'self-host' },
      { id: 'configuration', title: 'Configuration', keywords: 'environment variables secret key cors mongodb url' },
      { id: 'deploy', title: 'Deploy', keywords: 'docker compose vercel render tls proxy' },
      { id: 'database', title: 'Database', keywords: 'mongodb atlas replica set indexes postgres migration' },
      { id: 'first-operator', title: 'First operator', keywords: 'create_operator admin' },
      { id: 'catalog', title: 'Model catalog', keywords: 'approve artifacts' },
      { id: 'business-model', title: 'Payments and fees', keywords: 'no payments no commission direct provider payments legacy collections history' },
      { id: 'failover', title: 'Failover tuning', keywords: 'heartbeat timeout degraded recovery retry backoff pending attempts' },
      { id: 'sponsorships', title: 'Sponsorships and referrals', keywords: 'sponsored ads advertising campaign placement referral affiliate impressions clicks' },
      { id: 'monitoring', title: 'Monitoring', keywords: 'health ready metrics prometheus alerts' },
      { id: 'backups', title: 'Backups and recovery', keywords: 'mongodump restore runbook' },
      { id: 'worker-releases', title: 'Publishing worker releases', keywords: 'release tag signed updates' },
    ],
  },
  {
    href: '/docs/ai-agent',
    title: 'AI deployment agent',
    summary: 'The Gemini-powered deployment agent: how it works, configuration, limits and behaviour when Gemini is down.',
    sections: [
      { id: 'how-it-works', title: 'How it works', keywords: 'gemini agent architecture plan queue' },
      { id: 'gemini', title: 'Configure Gemini', keywords: 'gemini api key google ai studio gemini-2.5-flash' },
      { id: 'offline', title: 'When Gemini is unavailable', keywords: 'offline retry expire queue degraded' },
      { id: 'limits', title: 'Autonomy limits', keywords: 'budget spend duration recovery runtime source' },
      { id: 'testing', title: 'Tests', keywords: 'pytest fake gemini' },
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
      { id: 'not-verified', title: 'Not yet verified', keywords: 'gpu vllm docker macos replicas' },
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
