/**
 * Agent 状态管理
 */
import { create } from 'zustand';
import { api } from '@/lib/api';

interface Agent {
  id: string;
  name: string;
  description: string;
  status: string;
  model_id: string;
  health_score: number;
  created_at: string;
}

interface AgentState {
  agents: Agent[];
  currentAgent: Agent | null;
  loading: boolean;
  fetchAgents: () => Promise<void>;
  setCurrentAgent: (agent: Agent | null) => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  agents: [],
  currentAgent: null,
  loading: false,

  fetchAgents: async () => {
    set({ loading: true });
    try {
      const res = await api.get<Agent[]>('/agents');
      set({ agents: res.data || [], loading: false });
    } catch {
      set({ loading: false });
    }
  },

  setCurrentAgent: (agent) => set({ currentAgent: agent }),
}));
