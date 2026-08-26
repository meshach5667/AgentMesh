import Link from 'next/link';
export default function Home() {
  return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col items-center justify-center">
      <h1 className="text-5xl font-bold mb-4 text-blue-500">AgentMesh</h1>
      <p className="text-xl mb-8">Decentralized AI Compute Marketplace</p>
      <div className="flex gap-4">
        <Link href="/login" className="px-6 py-2 bg-blue-600 rounded-lg hover:bg-blue-700">Login</Link>
        <Link href="/register" className="px-6 py-2 bg-gray-700 rounded-lg hover:bg-gray-600">Register</Link>
      </div>
    </div>
  );
}