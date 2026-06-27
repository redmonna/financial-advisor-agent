"use client";

interface Agent {
  id: string;
  name: string;
  description: string;
  icon: string;
}

interface AgentSelectorProps {
  agents: Agent[];
  activeAgent: string;
  onSelect: (agentId: string) => void;
}

export function AgentSelector({
  agents,
  activeAgent,
  onSelect,
}: AgentSelectorProps) {
  return (
    <aside className="flex w-64 flex-col border-r border-white/10 bg-black/40">
      <div className="border-b border-white/10 px-4 py-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-white/60">
          Agents
        </h2>
      </div>
      <nav className="flex-1 space-y-1 p-2">
        {agents.map((agent) => (
          <button
            key={agent.id}
            onClick={() => onSelect(agent.id)}
            className={`flex w-full items-start gap-3 rounded-lg px-3 py-3 text-left transition-colors ${
              activeAgent === agent.id
                ? "bg-white/10 text-white"
                : "text-white/60 hover:bg-white/5 hover:text-white/80"
            }`}
          >
            <span className="text-xl">{agent.icon}</span>
            <div>
              <div className="text-sm font-medium">{agent.name}</div>
              <div className="text-xs text-white/40">{agent.description}</div>
            </div>
          </button>
        ))}
      </nav>
      <div className="border-t border-white/10 px-4 py-3">
        <p className="text-xs text-white/30">
          Select an agent to start a conversation
        </p>
      </div>
    </aside>
  );
}
