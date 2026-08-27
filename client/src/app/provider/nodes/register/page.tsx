'use client';
import { Card, CardHeader, CardTitle, CardContent } from '../../../../components/ui/Card';
import { Button } from '../../../../components/ui/Button';

export default function RegisterNodePage() {
  const command = `python -m node_agent register --control-plane-url https://api.agentmesh.network --owner-token abc123xyz`;
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Register New Node</h1>
      <Card>
        <CardHeader><CardTitle>Install Node Agent</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <p className="text-gray-300">Run the following command on your machine to register it to AgentMesh:</p>
          <div className="p-4 bg-black rounded-lg border border-gray-800 font-mono text-sm text-green-400">
            {command}
          </div>
          <Button onClick={() => navigator.clipboard.writeText(command)}>Copy Command</Button>
        </CardContent>
      </Card>
    </div>
  );
}
