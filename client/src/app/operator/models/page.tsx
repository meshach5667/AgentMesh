import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '../../../components/ui/Table';

export default function OperatorModels() {
  const dummyModels = [{ id: 'm1', name: 'Llama 3', is_approved: true }];
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Model Registry</h1>
      <Table>
        <TableHeader><TableRow><TableHead>ID</TableHead><TableHead>Name</TableHead><TableHead>Approved</TableHead></TableRow></TableHeader>
        <TableBody>
          {dummyModels.map(m => (
            <TableRow key={m.id}><TableCell>{m.id}</TableCell><TableCell>{m.name}</TableCell><TableCell>{m.is_approved ? 'Yes' : 'No'}</TableCell></TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
