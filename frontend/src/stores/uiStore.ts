/**
 * UI 状态管理
 */
import { create } from 'zustand';

interface UIState {
  sidebarCollapsed: boolean;
  theme: 'light' | 'dark';
  currentWorkspace: string | null;
  toggleSidebar: () => void;
  setTheme: (theme: 'light' | 'dark') => void;
  setWorkspace: (id: string | null) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  theme: (localStorage.getItem('theme') as 'light' | 'dark') || 'light',
  currentWorkspace: localStorage.getItem('workspace_id'),

  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setTheme: (theme) => {
    localStorage.setItem('theme', theme);
    set({ theme });
  },
  setWorkspace: (id) => {
    if (id) localStorage.setItem('workspace_id', id);
    else localStorage.removeItem('workspace_id');
    set({ currentWorkspace: id });
  },
}));
