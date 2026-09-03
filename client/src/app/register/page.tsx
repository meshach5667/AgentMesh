import { RegisterForm } from '../../components/auth/RegisterForm';

export default function RegisterPage() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 via-transparent to-purple-500/5" />
      <div className="relative z-10 w-full">
        <RegisterForm />
      </div>
    </div>
  );
}
