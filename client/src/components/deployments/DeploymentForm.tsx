'use client';
import React from 'react';
import { Button } from '../ui/button';
import { useState } from 'react';
import { useSubmitInference } from '../../hooks/useInference';

export function DeploymentForm({ modelId }: { modelId: string }) {
  const [prompt, setPrompt] = useState('');
  const inference = useSubmitInference();

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!prompt.trim()) return;
    inference.mutate({ model: modelId, input: { prompt: prompt.trim() } });
  };

  return (
    <form className="space-y-4" onSubmit={submit}>
      <p className="text-sm text-gray-300">Run an inference with model: {modelId}</p>
      <textarea
        value={prompt}
        onChange={(event) => setPrompt(event.target.value)}
        placeholder="Enter a prompt"
        className="min-h-32 w-full rounded-md border border-white/10 bg-black/20 p-3 text-sm"
        required
      />
      <Button type="submit" disabled={inference.isPending}>
        {inference.isPending ? 'Running...' : 'Run inference'}
      </Button>
      {inference.isError && <p className="text-sm text-red-400">{inference.error.message}</p>}
      {inference.data && (
        <pre className="whitespace-pre-wrap rounded-md bg-black/30 p-3 text-sm">
          {JSON.stringify(inference.data.result ?? inference.data, null, 2)}
        </pre>
      )}
    </form>
  );
}
