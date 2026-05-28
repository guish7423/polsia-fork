import { api, type Task } from "@/lib/api";
import { PageTitle, Text } from "@/components/PageTitle";

async function getTasks(): Promise<Task[]> {
  try {
    return await api.get<Task[]>("/tasks?limit=100");
  } catch {
    return [];
  }
}

const STATUS_STYLE: Record<string, string> = {
  completed: "bg-green-500/20 text-green-400",
  in_progress: "bg-blue-500/20 text-blue-400",
  pending: "bg-yellow-500/20 text-yellow-400",
  failed: "bg-red-500/20 text-red-400",
};

function StatusLabel({ status }: { status: string }) {
  const key = `status.${status}`;
  return <Text i18nKey={key} fallback={status} />;
}

export default async function TasksPage() {
  const tasks = await getTasks();

  return (
    <div className="p-6 space-y-4">
      <PageTitle i18nKey="tasks.title" />
      <div className="space-y-2">
        {tasks.length === 0 && (
          <p className="text-gray-400"><Text i18nKey="tasks.empty" /></p>
        )}
        {tasks.map((t) => (
          <div key={t.id} className="bg-gray-800 rounded-lg p-4 flex items-start justify-between gap-4">
            <div>
              <p className="text-white font-medium">{t.title}</p>
              <p className="text-gray-400 text-sm capitalize">
                {t.agent_type.replace(/_/g, " ")} · <Text i18nKey="tasks.priority" /> {t.priority}
              </p>
              <p className="text-gray-500 text-xs mt-1">
                {new Date(t.created_at).toLocaleString()}
              </p>
            </div>
            <span
              className={`flex-shrink-0 px-2 py-1 rounded text-xs font-medium ${STATUS_STYLE[t.status] ?? "bg-gray-700 text-gray-400"}`}
            >
              <StatusLabel status={t.status} />
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
