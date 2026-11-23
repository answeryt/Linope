import type { ComponentType } from "react";

interface DemoProps {
  tint?: number;
}

interface PropRow {
  defaultValue: string;
  description: string;
  name: string;
  type: string;
}

interface PropsSection {
  rows: PropRow[];
  title: string;
}

interface DocExample {
  component: ComponentType<DemoProps>;
  description: string;
  minHeight?: number;
  source: string;
  title: string;
}

interface ComponentDoc {
  demo: ComponentType<DemoProps>;
  demoMinHeight?: number;
  demoSource: string;
  description: string;
  examples?: DocExample[];
  props: PropsSection[];
  registryName: string;
  slug: string;
  tintable?: boolean;
  tintNote?: string;
  title: string;
}

export type { ComponentDoc, DemoProps, DocExample, PropRow, PropsSection };
