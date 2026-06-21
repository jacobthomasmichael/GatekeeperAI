import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";

export default function AccountLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto bg-gray-50 dark:bg-slate-950 p-8">
          {children}
        </main>
      </div>
    </AuthGuard>
  );
}
