import { api } from "@/lib/api";
import { PageTitle, Text } from "@/components/PageTitle";

type Prospect = { id: number; email: string; first_name: string | null; company: string | null; status: string; created_at: string };

async function getProspects() {
  try { return await api.get<Prospect[]>("/outreach/prospects?limit=100"); } catch { return []; }
}

const STATUS_STYLE: Record<string, string> = {
  new: "text-blue-400", contacted: "text-yellow-400", replied: "text-green-400",
  converted: "text-indigo-400", unsubscribed: "text-gray-400",
};

export default async function OutreachPage() {
  const prospects = await getProspects();
  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-2">
        <PageTitle i18nKey="outreach.title" />
        <span className="text-gray-400 text-lg">({prospects.length})</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead>
            <tr className="text-gray-400 border-b border-gray-700">
              <th className="pb-2 pr-4">Email</th>
              <th className="pb-2 pr-4"><Text i18nKey="settings.company_name" /></th>
              <th className="pb-2 pr-4">Company</th>
              <th className="pb-2"><Text i18nKey="memory.category" /></th>
            </tr>
          </thead>
          <tbody>
            {prospects.map((p) => (
              <tr key={p.id} className="border-b border-gray-800">
                <td className="py-2 pr-4 text-white">{p.email}</td>
                <td className="py-2 pr-4 text-gray-300">{p.first_name ?? "—"}</td>
                <td className="py-2 pr-4 text-gray-300">{p.company ?? "—"}</td>
                <td className={`py-2 capitalize ${STATUS_STYLE[p.status] ?? "text-gray-400"}`}>{p.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {prospects.length === 0 && <p className="text-gray-400 mt-4"><Text i18nKey="outreach.empty" /></p>}
      </div>
    </div>
  );
}
