/// <reference types="vite/client" />

declare module "*.css";

declare module "*.jpg" {
  const src: string;
  export default src;
}

declare module "virtual:capability-desktops" {
  import type { ComponentType } from "react";

  export type CapabilityDesktopProps = {
    capability?: string;
    messages?: Array<{
      id: string;
      reasoning?: string;
      role: "assistant" | "error" | "system" | "user";
      stream?: boolean;
      text: string;
    }>;
    process?: {
      activity: "away" | "busy" | "waiting";
      capability: string;
      id: string;
    } | null;
    tasks?: Array<{
      id: string;
      leader: boolean;
      pc: string;
      pid: string;
      registers: Record<string, unknown>;
    }>;
    conversations?: Array<{
      id: string;
      pid: string;
      queued: number;
      running: boolean;
    }>;
    selectedId?: string;
    onSelectConversation?: (id: string) => void;
    onCreateConversation?: () => void;
  };

  export const desktops: Record<string, ComponentType<CapabilityDesktopProps>>;
  export const loops: Record<string, string>;
}

interface LinopeKernelApi {
  chat: {
    send(text: string): string;
  };
  process: {
    send(input: { pid: number; text: string; addresses?: string[] }): string;
    create(input: {
      capability: string;
      changes?: Array<{ topic: string; value: string }>;
      count?: number;
      cwd?: string;
      maxRuntimeSeconds?: number;
      shares?: string[];
      with?: Array<{ kind: string; identity: string }>;
      once?: boolean;
      ping?: boolean;
      envFile?: string;
      envKeys?: string[];
    }): string;
  };
  environment: {
    load(input: { path: string; keys?: string[] }): string;
    saveSecret(input: { key: string; value: string }): string;
  };
  model: {
    catalog(): string;
    configure(input: {
      cores?: number;
      capability?: string;
      changes?: Array<{ topic: string; value: string }>;
    }): string;
  };
  memory: {
    configure(input: { backend: "memory" | "local"; path?: string }): string;
  };
  stop(): void;
  onEvent(callback: (event: unknown) => void): () => void;
}

interface Window {
  linopeKernel?: LinopeKernelApi;
}
